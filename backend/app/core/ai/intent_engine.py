# backend/app/core/ai/intent_engine.py
from __future__ import annotations
import os, json, requests, re
from typing import Dict, Any

# =====================================================
# DeepSeek / OpenAI Config
# =====================================================
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

# =====================================================
# SYSTEM PROMPT：最强意图分类器
# =====================================================
INTENT_SYSTEM_PROMPT = """
你是 DriftSystem（心悦宇宙）的“玩家意图分类器”。
你必须返回严格 JSON，不得包含解释或多余文本。

可识别意图：

======【世界类】======
- SET_DAY
- SET_NIGHT
- SET_WEATHER
- TELEPORT
- MOVE_TO

======【造物类】======
- SPAWN_ENTITY
- BUILD_STRUCTURE
- CHANGE_ENV

======【剧情类】======
- NEXT_LEVEL
- GOTO_LEVEL
- STORY_CONTINUE
- OPEN_MINIMAP

======【普通聊天】======
- SAY_ONLY

输出格式：
{
  "type": "...",
  "entity": "...可选",
  "structure": "...可选",
  "level_id": "...可选",
  "weather": "...可选",
  "time": "...可选",
  "raw_text": "玩家原文"
}
"""

# =====================================================
# 调用 DeepSeek
# =====================================================
def _deepseek_intent(text: str) -> Dict[str, Any]:
    if not API_KEY:
        return {"type": "SAY_ONLY", "raw_text": text}

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
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
            timeout=10,
        ).json()

        parsed = json.loads(resp["choices"][0]["message"]["content"])
        parsed["raw_text"] = text
        return parsed

    except Exception as e:
        print("[intent_engine] AI error → fallback", e)
        return {"type": "SAY_ONLY", "raw_text": text}


# =====================================================
# fallback 规则
# =====================================================
def _fallback_intent(text: str, story_engine) -> Dict[str, Any]:
    raw = text.strip()

    # minimap
    if "地图" in raw or "小地图" in raw:
        return {"type": "OPEN_MINIMAP", "raw_text": raw}

    # time
    if "白天" in raw or "天亮" in raw:
        return {"type": "SET_DAY", "raw_text": raw}
    if "夜" in raw or "晚上" in raw:
        return {"type": "SET_NIGHT", "raw_text": raw}

    # weather
    if "雨" in raw:
        return {"type": "SET_WEATHER", "weather": "rain", "raw_text": raw}
    if "雷" in raw:
        return {"type": "SET_WEATHER", "weather": "thunder", "raw_text": raw}
    if "晴" in raw:
        return {"type": "SET_WEATHER", "weather": "clear", "raw_text": raw}

    # NEXT LEVEL
    if "下一关" in raw or "进入下一关" in raw or "继续剧情" in raw:
        level = story_engine.minimap.recommended_next("default")
        return {"type": "NEXT_LEVEL", "level_id": level, "raw_text": raw}

    # GOTO LEVEL
    m = re.search(r"level[_\s-]?(\d{1,2})", raw.lower())
    if m:
        level_id = f"level_{int(m.group(1)):02d}"
        if level_id in story_engine.graph.all_levels():
            return {"type": "GOTO_LEVEL", "level_id": level_id, "raw_text": raw}

    # spawn entity
    if any(w in raw for w in ["猫","兔","狗","羊","npc","僵尸"]):
        return {"type": "SPAWN_ENTITY", "entity": raw, "raw_text": raw}

    # build
    if any(w in raw for w in ["房子","屋","桥","平台","塔","柱"]):
        return {"type": "BUILD_STRUCTURE", "structure": raw, "raw_text": raw}

    return {"type": "SAY_ONLY", "raw_text": raw}


# =====================================================
# 主入口：解析意图
# =====================================================
def parse_intent(player_id: str, text: str, world_state, story_engine):
    text = text.strip()
    if not text:
        return {"type": "SAY_ONLY", "raw_text": text}

    ai = _deepseek_intent(text)

    if ai.get("type") not in ["UNKNOWN", None]:
        return ai

    return _fallback_intent(text, story_engine)