# backend/app/api/story_api.py
from fastapi import APIRouter, Query
from typing import Optional

from app.core.story.story_engine import story_engine

router = APIRouter(prefix="/story", tags=["Story"])

@router.get("/state")
def story_state(player_id: Optional[str] = Query(default=None)):
    return story_engine.get_public_state(player_id)

@router.get("/history")
def story_history(player_id: str):
    return {
        "player_id": player_id,
        "history": story_engine.get_history(player_id)
    }

@router.post("/clear")
def story_clear(player_id: str):
    story_engine.clear_history(player_id)
    return {"status": "ok", "player_id": player_id}