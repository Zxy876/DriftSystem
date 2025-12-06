# backend/app/core/ai/intent_engine.py
from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, Optional, List
import requests

API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

# ============================================================
# Prompt：新版（要求返回 intents[]）
# ============================================================
INTENT_PROMPT = """
你是“心悦宇宙多意图解析器”。
必须输出 JSON，结构固定为：

{
  "intents": [
      { "type": "...", ... },
      { "type": "...", ... }
  ]
}

支持的意图（type）：

- CREATE_STORY
- SHOW_MINIMAP
- SET_DAY / SET_NIGHT
- SET_WEATHER
- TELEPORT
- SPAWN_ENTITY
- BUILD_STRUCTURE
- GOTO_LEVEL
- GOTO_NEXT_LEVEL
- STORY_CONTINUE
- SAY_ONLY

规则：

1. 若一句话包含多个动作（如：跳到第三关并把天气改成白天），则必须输出多个 intents。
2. 出现以下词 → 必须加入 CREATE_STORY：
   “写剧情”“写故事”“编故事”“创造剧情”“生成剧情”“做一个关卡”
3. 涉及关卡数字必须解析成 level_01 / level_05 形式。
4. 若 AI 不确定，只输出一个 { "type": "SAY_ONLY" }。

严格只允许 JSON。
"""

# ============================================================
# level 解析
# ============================================================
def normalize_level(text: str) -> Optional[str]:
    raw = text.lower()
    m = re.search(r"\d+", raw)
    if m:
        return f"level_{int(m.group()):02d}"

    cn = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
    for k,v in cn.items():
        if k+"关" in text:
            return f"level_{v:02d}"
    return None

# ============================================================
# AI 多意图解析
# ============================================================
def ai_parse_multi(text: str) -> Optional[List[Dict[str, Any]]]:
    if not API_KEY:
        return None

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=12,
        ).json()

        data = json.loads(resp["choices"][0]["message"]["content"])
        return data.get("intents", [])
    except Exception as e:
        print("[intent_engine] AI multi-intent failed:", e)
        return None

# ============================================================
# fallback：返回 list
# ============================================================
def fallback_intents(text: str) -> List[Dict[str, Any]]:
    raw = text.strip()
    intents = []

    # CREATE_STORY
    if ("剧情" in raw or "故事" in raw or "关卡" in raw) and \
       ("写" in raw or "生成" in raw or "创造" in raw):
        intents.append({
            "type": "CREATE_STORY",
            "title": raw[:12],
            "text": raw,
            "raw_text": raw,
        })
        return intents

    # minimap - 扩展自然语言触发词
    if any(w in raw for w in ["地图", "minimap", "看地图", "小地图", "导航", "周围", "位置", "在哪", "地图在哪", "显示地图", "查看地图", "看看周围"]):
        intents.append({"type": "SHOW_MINIMAP", "raw_text": raw})

    # time/weather
    if "白天" in raw:
        intents.append({"type": "SET_DAY"})
    if "晚上" in raw or "夜" in raw:
        intents.append({"type": "SET_NIGHT"})
    if "雨" in raw:
        intents.append({"type": "SET_WEATHER", "weather": "rain"})

    # level
    lvl = normalize_level(raw)
    if lvl:
        intents.append({"type": "GOTO_LEVEL", "level_id": lvl})

    if not intents:
        intents.append({"type": "SAY_ONLY", "raw_text": raw})

    return intents


# ============================================================
# parse_intent → 输出 { status, intents: [] }
# ============================================================
def parse_intent(player_id, text, world_state, story_engine):

    ai_list = ai_parse_multi(text)
    intents = ai_list if ai_list else fallback_intents(text)

    # 修正 level 格式
    for it in intents:
        if it.get("type") == "GOTO_LEVEL":
            lvl1 = it.get("level_id")
            lvl2 = it.get("level")
            if lvl1:
                it["level_id"] = lvl1
            elif lvl2:
                it["level_id"] = normalize_level(lvl2)
            it.pop("level", None)

    # 附加 minimap （给所有 intents）
    for it in intents:
        it["minimap"] = story_engine.minimap.to_dict(player_id)

    # 自动补世界 patch
    for it in intents:
        t = it["type"]
        if t == "SET_DAY":
            it["world_patch"] = {"mc": {"time": "day"}}
        elif t == "SET_NIGHT":
            it["world_patch"] = {"mc": {"time": "night"}}
        elif t == "SET_WEATHER":
            w = it.get("weather", "clear")
            it["world_patch"] = {"mc": {"weather": w}}

        elif t == "TELEPORT":
            it["world_patch"] = {"mc": {
                "teleport": {"mode": "relative", "x": 0, "y": 0, "z": 3}
            }}

    # CREATE_STORY 自动补全
    for it in intents:
        if it["type"] == "CREATE_STORY":
            it.setdefault("title", text[:12] or "新剧情")
            it.setdefault("text", text)
            it.setdefault("world_patch", {
                "mc": {
                    "spawn": {
                        "type": "villager",
                        "name": "桃子",
                        "offset": {"dx": 2, "dy": 0, "dz": 2}
                    },
                    "tell": "✨ 新剧情已准备好，正在加载……"
                }
            })

    return {
        "status": "ok",
        "intents": intents
    }