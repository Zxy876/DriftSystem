# app/api/world_api.py

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.core.world.engine import WorldEngine

router = APIRouter()

# -------------------------------------
# 世界引擎：全局唯一
# -------------------------------------
world = WorldEngine()

class WorldAction(BaseModel):
    action: dict


# -------------------------------------
# GET /world/state
# -------------------------------------
@router.get("/state")
def get_state():
    return JSONResponse(content=world.export())


# -------------------------------------
# POST /world/apply
# -------------------------------------
@router.post("/apply")
def apply_action(data: WorldAction):
    result = world.apply(data.action)
    return JSONResponse(content=result)


# -------------------------------------
# POST /world/tick
# 推进世界物理：dt 可选（默认 0.05）
# -------------------------------------
class TickRequest(BaseModel):
    dt: float | None = 0.05    # 可不传，默认 0.05


@router.post("/tick")
def update_world(req: TickRequest):
    new_state = world.tick(dt=req.dt)
    return JSONResponse(content={
        "status": "ok",
        "dt": req.dt,
        "variables": new_state
    })