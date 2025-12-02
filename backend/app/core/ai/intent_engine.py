# backend/app/core/ai/intent_engine.py
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import requests

API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

INTENT_PROMPT = """
你是“心悦宇宙”的意图解析器。玩家说一句话，你返回 JSON 表示意图。

必须只返回 JSON，没有解释。

可用意图：

- SHOW_MINIMAP

- SET_DAY
- SET_NIGHT
- SET_WEATHER   # 参数：weather
- TELEPORT      # 参数：可选坐标
- SPAWN_ENTITY  # 参数：entity
- BUILD_STRUCTURE  # 参数：structure / shape / size

- GOTO_LEVEL       # 参数：level_id
- GOTO_NEXT_LEVEL
- STORY_CONTINUE   # 表达希望继续剧情
- SAY_ONLY         # 普通聊天 / 表达

level_id 必须返回标准格式：level_XX，例如 “第八关” = “level_08”。

天气可返回：
- clear
- rain
- thunder

示例输入：
“带我去第一关”
示例输出：
{ "type": "GOTO_LEVEL", "level_id": "level_01", "raw_text": "带我去第一关" }

示例输入：
“天气晴朗一点”
示例输出：
{ "type": "SET_WEATHER", "weather": "clear", "raw_text": "天气晴朗一点" }

**必须严格输出 JSON。**
"""


def normalize_level(text: str) -> Optional[str]:
    raw = text.lower()
    m = re.search(r"\d+", raw)
    if m:
        num = int(m.group())
        return f"level_{num:02d}"

    cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    for k, v in cn.items():
        if k + "关" in text:
            return f"level_{v:02d}"
    return None


# ------------------------ 调 DeepSeek ------------------------
def ai_parse_intent(text: str) -> Optional[Dict[str, Any]]:
    if not API_KEY:
        return {"type": "SAY_ONLY", "raw_text": text}

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=12,
        ).json()

        return json.loads(resp["choices"][0]["message"]["content"])
    except Exception as e:
        print("[intent_engine] AI intent failed:", e)
        return None


# ------------------------ fallback ------------------------
def fallback_intent(text: str) -> Dict[str, Any]:
    raw = text.strip()

    if "白天" in raw:
        return {"type": "SET_DAY", "raw_text": raw}
    if "晚上" in raw or "夜" in raw:
        return {"type": "SET_NIGHT", "raw_text": raw}
    if "雨" in raw:
        return {"type": "SET_WEATHER", "weather": "rain", "raw_text": raw}
    if "地图" in raw:
        return {"type": "SHOW_MINIMAP", "raw_text": raw}

    lvl = normalize_level(raw)
    if lvl:
        return {"type": "GOTO_LEVEL", "level_id": lvl, "raw_text": raw}

    return {"type": "SAY_ONLY", "raw_text": raw}


# ------------------------ 总入口 ------------------------
def parse_intent(
    player_id: str,
    text: str,
    world_state: Dict[str, Any],
    story_engine,
) -> Dict[str, Any]:
    """
    只做“意图分类 + 附加 minimap”，不推进剧情。
    剧情推进交给 /world/apply（由 MC 插件在 SAY_ONLY / STORY_CONTINUE 时调用）。
    """
    ai_result = ai_parse_intent(text)
    if ai_result and "type" in ai_result:
        intent = ai_result
    else:
        intent = fallback_intent(text)

    # 附加 minimap 信息（供传送 / 展示使用）
    intent["minimap"] = story_engine.minimap.to_dict(player_id)
    return intent