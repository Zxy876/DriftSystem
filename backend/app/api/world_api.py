from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.world.engine import WorldEngine
from app.core.story.story_engine import story_engine

router = APIRouter(prefix="/world", tags=["World"])
world_engine = WorldEngine()

class MoveAction(BaseModel):
    x: float
    y: float
    z: float
    speed: float = 0.0
    moving: bool = False

class WorldAction(BaseModel):
    move: Optional[MoveAction] = None
    say: Optional[str] = None  # 聊天输入

class ApplyInput(BaseModel):
    action: WorldAction
    player_id: Optional[str] = "default"

class WorldApplyResponse(BaseModel):
    status: str
    world_state: Dict[str, Any]
    ai_option: Optional[int] = None
    story_node: Optional[Dict[str, Any]] = None
    world_patch: Optional[Dict[str, Any]] = None  # ✅ 新增

@router.get("/state")
def get_world_state():
    return world_engine.get_state()

@router.post("/apply", response_model=WorldApplyResponse)
def apply_action(inp: ApplyInput):
    action_dict = inp.action.dict(exclude_none=True)

    new_state = world_engine.apply(action_dict)

    ai_option = None
    story_node = None
    world_patch = None

    if story_engine.should_advance(inp.player_id, new_state, action_dict):
        ai_option, story_node, world_patch = story_engine.advance(inp.player_id, new_state, action_dict)
        # ✅ AI patch 真正影响世界
        if world_patch:
            new_state = world_engine.apply_patch(world_patch)

    return WorldApplyResponse(
        status="ok",
        world_state=new_state,
        ai_option=ai_option,
        story_node=story_node,
        world_patch=world_patch
    )