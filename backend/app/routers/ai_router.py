# backend/app/routers/ai_router.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict, Optional

from app.core.ai.intent_engine import parse_intent
from app.core.story.story_engine import story_engine

router = APIRouter(prefix="/ai", tags=["AI"])


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
    玩家一句自然语言 → 解析为意图 JSON
    （只做意图分类 + 附加 minimap，不推进剧情）
    """
    intent = parse_intent(
        player_id=req.player_id,
        text=req.text,
        world_state=req.world_state or {},
        story_engine=story_engine,
    )

    return IntentResponse(status="ok", intent=intent)