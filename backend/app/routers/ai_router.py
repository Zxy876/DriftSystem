# backend/app/routers/ai_router.py
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter
from pydantic import BaseModel

# ------------------------
# Intent Engine (NEW)
# ------------------------
from app.core.ai.intent_engine import parse_intent
from app.core.story.story_engine import story_engine

router = APIRouter(prefix="/ai", tags=["ai"])


# ============================================================
# 1. DSL 解释器（旧功能，保持不动）
# ============================================================
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

if not API_KEY:
    print("[ai_router] WARNING: OPENAI_API_KEY / DEEPSEEK_API_KEY 未配置，AI 路由将只返回占位结果。")


class AiInput(BaseModel):
    player_id: str
    message: str
    world_state: Dict[str, Any] | None = None


def call_deepseek(message: str) -> Dict[str, Any]:
    """
    原本的自然语言 → DSL 通道（保持）
    """
    if not API_KEY:
        return {
            "reply": "（后端未配置 AI 密钥，目前使用占位回复。）",
            "dsl": ""
        }

    system_prompt = """
    你是“心悦宇宙 · DSL 解释器”。

    玩家会用自然语言和你说话，你需要：
    1. 温柔回复玩家（reply 字段）
    2. 用 DSL 描述世界行动（dsl 字段）

    DSL 示例:
    - set time night
    - weather rain
    - tp player 0 80 0
    - story next
    - spawn villager at 2 0

    必须输出 JSON:
    {"reply": "...", "dsl": "..."}
    """

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "temperature": 0.4,
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return json.loads(text)
    except Exception as e:
        print("[ai_router] call_deepseek error:", e)
        return {
            "reply": f"我暂时连不上 AI 服务器：{e}",
            "dsl": "",
        }


@router.post("/route/{player_id}")
def ai_route(player_id: str, data: AiInput):
    """
    原始 DSL 模式 API（保持）
    """
    result = call_deepseek(data.message)

    return {
        "status": "ok",
        "player_id": player_id,
        "reply": result.get("reply", ""),
        "dsl": result.get("dsl", ""),
    }


# ============================================================
# 2. Phase 3 新功能：自然语言 → 意图 JSON
# ============================================================

class IntentRequest(BaseModel):
    player_id: str = "default"
    text: str
    world_state: Optional[Dict[str, Any]] = None


class IntentResponse(BaseModel):
    status: str
    intent: Dict[str, Any]


@router.post("/intent", response_model=IntentResponse)
def ai_intent(req: IntentRequest):
    """
    Phase 3: 心悦宇宙的「玩家一句话 → 意图 JSON」
    
    示例：
    - “带我去下一关！”
    - “打开小地图”
    - “去 level_08”
    - “我想继续自由探索”
    """
    intent = parse_intent(
        player_id=req.player_id,
        text=req.text,
        world_state=req.world_state or {},
        story_engine=story_engine,
    )

    return IntentResponse(status="ok", intent=intent)