# backend/app/api/world_api.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.world.engine import WorldEngine
from app.core.story.story_engine import story_engine
from app.core.world.trigger import trigger_engine, TriggerPoint
from app.core.ai.intent_engine import parse_intent

router = APIRouter(prefix="/world", tags=["World"])
world_engine = WorldEngine()

# ============================================================
# Data Models
# ============================================================
class MoveAction(BaseModel):
    x: float
    y: float
    z: float
    speed: float = 0.0
    moving: bool = False

class WorldAction(BaseModel):
    move: Optional[MoveAction] = None
    say: Optional[str] = None

class ApplyInput(BaseModel):
    action: WorldAction
    player_id: Optional[str] = "default"

class WorldApplyResponse(BaseModel):
    status: str
    world_state: Dict[str, Any]
    ai_option: Optional[int] = None
    story_node: Optional[Dict[str, Any]] = None
    world_patch: Optional[Dict[str, Any]] = None
    trigger: Optional[Dict[str, Any]] = None

# ============================================================
# Routes
# ============================================================
@router.post("/apply", response_model=WorldApplyResponse)
def apply_action(inp: ApplyInput):

    player_id = inp.player_id
    act = inp.action.dict(exclude_none=True)

    # 1️⃣ 世界状态更新
    new_state = world_engine.apply(act)
    vars_ = new_state.get("variables") or {}
    x, y, z = vars_.get("x", 0), vars_.get("y", 0), vars_.get("z", 0)

    # 2️⃣ 先解析意图（玩家说话）
    say_text = act.get("say")
    intent = None
    if say_text:
        intent = parse_intent(player_id, say_text, new_state, story_engine)

    # =============== 处理 Intent =======================
    if intent:

        t = intent["type"]

        # ------- NEXT LEVEL -------
        if t == "NEXT_LEVEL":
            level_id = intent["level_id"]
            patch = story_engine.load_level_for_player(player_id, level_id)
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(
                status="ok", world_state=new_state,
                story_node={"title": "下一关", "text": f"进入 {level_id}"},
                world_patch=patch
            )

        # ------- GOTO LEVEL -------
        if t == "GOTO_LEVEL":
            level_id = intent["level_id"]
            patch = story_engine.load_level_for_player(player_id, level_id)
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(
                status="ok", world_state=new_state,
                story_node={"title": "前往关卡", "text": f"跳转到 {level_id}"},
                world_patch=patch
            )

        # ------- 小地图 -------
        if t == "OPEN_MINIMAP":
            mm = story_engine.minimap.to_dict(player_id)
            return WorldApplyResponse(
                status="ok", world_state=new_state,
                story_node={"title": "小地图", "text": "显示小地图"},
                world_patch={"minimap": mm}
            )

        # ------- 时间 -------
        if t == "SET_DAY":
            patch = {"mc": {"time": "day"}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

        if t == "SET_NIGHT":
            patch = {"mc": {"time": "night"}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

        # ------- 天气 -------
        if t == "SET_WEATHER":
            patch = {"mc": {"weather": intent["weather"]}}
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

        # ------- 造物 -------
        if t == "SPAWN_ENTITY":
            patch = {
                "mc": {
                    "spawn": {
                        "type": "rabbit",
                        "name": intent["entity"],
                        "offset": {"dx": 1, "dy": 0, "dz": 1}
                    }
                }
            }
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

        # ------- 建筑 -------
        if t == "BUILD_STRUCTURE":
            patch = {
                "mc": {
                    "build": {
                        "shape": "platform",
                        "material": "oak_planks",
                        "size": 5,
                        "safe_offset": {"dx": 2, "dy": 0, "dz": 2}
                    }
                }
            }
            new_state = world_engine.apply_patch(patch)
            return WorldApplyResponse(status="ok", world_state=new_state, world_patch=patch)

    # 3️⃣ 坐标触发器（进入关卡）
    tp = trigger_engine.check(player_id, x, y, z)
    if tp and tp.action == "load_level":
        patch = story_engine.load_level_for_player(player_id, tp.level_id)
        new_state = world_engine.apply_patch(patch)
        return WorldApplyResponse(
            status="ok",
            world_state=new_state,
            story_node={"title": "世界触发点", "text": f"成功加载 {tp.level_id}"},
            world_patch=patch,
            trigger={"id": tp.id, "level_id": tp.level_id}
        )

    # 4️⃣ 默认
    return WorldApplyResponse(status="ok", world_state=new_state)