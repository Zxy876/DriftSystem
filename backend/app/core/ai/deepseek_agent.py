# backend/app/core/ai/deepseek_agent.py
from __future__ import annotations

import os
import json
import time
import hashlib
import threading
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}" if API_KEY else "",
    "Content-Type": "application/json",
}

# ---------- 全局节流 + 缓存 ----------
_lock = threading.Lock()
_LAST_CALL_TS: Dict[str, float] = {}
_CACHE: Dict[str, Dict[str, Any]] = {}

# 每个玩家最短 AI 调用间隔（秒）
MIN_INTERVAL = 5.0

# 缓存最多保存多少条 key -> 结果（简单 LRU 近似）
MAX_CACHE_SIZE = 128


SYSTEM_PROMPT = """
你是《昆明湖宇宙》的“造物主（Story + World God）”。

你必须只输出严格合法 JSON，不输出解释文本。

你的任务：
1) 生成连贯剧情 node（title,text）
2) 生成 world_patch，使剧情在 MC 世界中真实发生
3) 尊重玩家输入（say）和事件树(tree_state)
4) 避免把玩家传送到方块内部，避免窒息/掉虚空
5) 当剧情提到具体人物/动物/NPC时，应尽量使用 spawn 生成实体

mc 支持字段：
{
  "tell": "给玩家的一句话(可选)",
  "teleport": {"mode":"relative|absolute","x":0,"y":0,"z":0},
  "effect": {"type":"LEVITATION|GLOW|BLINDNESS|SPEED|SLOW|WITHER",
             "seconds":5,"amplifier":1},
  "time": "day|night|noon|midnight",
  "weather": "clear|rain|thunder",
  "build": {
      "shape":"house|bridge|pillar|platform",
      "material":"oak_planks|stone|glass|white_wool|...mc方块id",
      "size": 5,
      "safe_offset": {"dx":2,"dy":0,"dz":2}
  },
  "spawn": {
      "type":"villager|rabbit|fox|cat|allay|armor_stand|...",
      "name":"显示名(可选)",
      "offset":{"dx":1,"dy":0,"dz":1}
  },
  "ending": {"type":"good|bad|neutral","reason":"一句话"}
}

强制规则：
- 玩家 say 含义 = “上天/飞起来/升空/我要飞”，必须 effect=LEVITATION 或 teleport.y>=10。
- 若剧情中出现“嫦娥/玉兔/主人公/某某人物/动物”：
    → 必须生成 spawn，让玩家看到实体。
- 生成建筑(build) 时必须 safe_offset(dx>=2或dz>=2)。
- 不要输出未定义字段。
"""


def _make_cache_key(context: Dict[str, Any], messages_history: List[Dict[str, str]]) -> str:
    """
    用 context + 最近几条对话构造一个稳定的 key。
    """
    key_payload = {
        "context": context,
        "messages_tail": messages_history[-8:],
    }
    s = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Dict[str, Any] | None:
    with _lock:
        return _CACHE.get(key)


def _cache_put(key: str, value: Dict[str, Any]) -> None:
    with _lock:
        if len(_CACHE) >= MAX_CACHE_SIZE:
            # 简单丢弃最早的一条
            first_key = next(iter(_CACHE.keys()))
            _CACHE.pop(first_key, None)
        _CACHE[key] = value


def deepseek_decide(context: Dict[str, Any], messages_history: List[Dict[str, Dict[str, str]]]) -> Dict[str, Any]:
    """
    DriftSystem 主 AI 调度器（有节流 + 缓存）：
    - context 中必须包含 player_id（由 StoryEngine 提供）
    - 若在冷却时间内，则直接返回“静默帧”，不访问远程 LLM
    - 若命中缓存（相同 context + 对话尾部），直接复用结果
    """
    player_id = str(context.get("player_id") or "global")

    now = time.time()
    with _lock:
        last = _LAST_CALL_TS.get(player_id, 0.0)
        in_cooldown = (now - last) < MIN_INTERVAL

    if in_cooldown:
        # 冷却期间：返回一个“节奏帧”，不访问 AI
        return {
            "option": None,
            "node": {
                "title": "昆明湖 · 静默帧",
                "text": "风在湖面打着圈，你感觉世界在蓄力，而不是停下。"
            },
            "world_patch": {
                "variables": {},
                "mc": {}
            }
        }

    # ---------- 尝试命中缓存 ----------
    cache_key = _make_cache_key(context, messages_history)
    cached = _cache_get(cache_key)
    if cached is not None:
        with _lock:
            _LAST_CALL_TS[player_id] = now
        return cached

    # ---------- 真正调用远程 LLM ----------
    if not API_KEY:
        # 无密钥：直接返回一个占位剧情节点
        fallback = {
            "option": None,
            "node": {
                "title": "昆明湖 · 本地风声",
                "text": "此刻没有连上 AI 服务器，但你仍能在湖边思考下一步要做什么。"
            },
            "world_patch": {
                "variables": {},
                "mc": {"tell": "（后端未配置 AI 密钥，使用占位剧情）"}
            }
        }
        return fallback

    user_prompt = f"""
    根据玩家状态、行动、tree_state 和历史剧情，生成下一段剧情，并给出 world_patch。

    严格返回 JSON：
    {{
      "option": 0/1/2/... 或 null,
      "node": {{
          "title": "...",
          "text": "..."
      }},
      "world_patch": {{
          "variables": {{ ...可选... }},
          "mc": {{ ...可选... }}
      }}
    }}

    当前输入 context:
    {json.dumps(context, ensure_ascii=False)}
    """

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += messages_history[-12:]
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.8,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=20,  # 比原来 40 更短，避免长时间卡住
        )
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
        parsed = json.loads(raw)

        _cache_put(cache_key, parsed)
        with _lock:
            _LAST_CALL_TS[player_id] = time.time()

        return parsed

    except Exception as e:
        print("[AI ERROR deepseek_decide]", e)
        # 出错：返回一个安全的占位剧情
        fallback = {
            "option": None,
            "node": {
                "title": "昆明湖 · 静默",
                "text": "AI 沉默了一瞬，但湖面的风仍提醒你：故事没有断。"
            },
            "world_patch": {
                "variables": {},
                "mc": {"tell": "（AI超时或出错）"}
            }
        }
        with _lock:
            _LAST_CALL_TS[player_id] = time.time()
        return fallback
