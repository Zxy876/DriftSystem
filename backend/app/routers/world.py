from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict, Optional

from app.core.story.story_engine import story_engine

router = APIRouter(prefix="/world", tags=["world"])

class ApplyReq(BaseModel):
    player_id: str
    action: Dict[str, Any]
    world_state: Dict[str, Any] = {}

@router.post("/apply")
def apply(req: ApplyReq):
    player_id = req.player_id
    action = req.action or {}
    world_state = req.world_state or {}

    say = action.get("say","")

    # ---------- level command ----------
    if isinstance(say, str) and say.strip().startswith("/level"):
        # 例：/level 001
        parts = say.strip().split()
        if len(parts) >= 2:
            level_id = parts[1]
            patch = story_engine.load_level_for_player(player_id, f"level_{level_id}")
            return {
                "status":"ok",
                "story_node":{
                    "title":"关卡加载",
                    "text":f"已加载关卡 {level_id}，你听见世界开始呼吸。"
                },
                "world_patch": patch,
                "ai_option": None
            }
        return {
            "status":"ok",
            "story_node":{"title":"关卡加载","text":"用法：/level 001"},
            "world_patch":{"mc":{"tell":"用法：/level 001"}},
            "ai_option": None
        }

    # ---------- normal AI advance ----------
    if not story_engine.should_advance(player_id, world_state, action):
        return {"status":"ok","world_patch":{},"story_node":None,"ai_option":None}

    option, node, patch = story_engine.advance(player_id, world_state, action)

    return {
        "status":"ok",
        "ai_option": option,
        "story_node": node,
        "world_patch": patch,
        "world_state": story_engine.get_public_state(player_id)
    }