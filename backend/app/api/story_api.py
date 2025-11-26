# backend/app/api/story_api.py
from fastapi import APIRouter
from typing import Dict, Any

from app.core.story.story_loader import list_levels, load_level
from app.core.story.story_engine import story_engine

router = APIRouter(prefix="/story")

@router.get("/levels")
def api_story_levels():
    return {"status":"ok", "levels": list_levels()}

@router.get("/level/{level_id}")
def api_story_level(level_id: str):
    try:
        lv = load_level(level_id)
        return {"status":"ok", "level": lv.__dict__}
    except FileNotFoundError:
        return {"status":"error", "msg": f"Level {level_id} not found"}

@router.post("/load/{player_id}/{level_id}")
def api_story_load(player_id: str, level_id: str):
    """
    给某个玩家加载关卡
    """
    try:
        patch = story_engine.load_level_for_player(player_id, level_id)
        return {"status":"ok", "msg": f"{level_id} loaded", "bootstrap_patch": patch}
    except FileNotFoundError:
        return {"status":"error", "msg": f"Level {level_id} not found"}

@router.post("/advance/{player_id}")
def api_story_advance(player_id: str, payload: Dict[str, Any]):
    """
    payload: {"world_state": {...}, "action": {...}}
    """
    world_state = payload.get("world_state", {}) or {}
    action = payload.get("action", {}) or {}

    option, node, patch = story_engine.advance(player_id, world_state, action)
    return {
        "status": "ok",
        "option": option,
        "node": node,
        "world_patch": patch
    }

@router.get("/state/{player_id}")
def api_story_state(player_id: str):
    return {"status":"ok", "state": story_engine.get_public_state(player_id)}