from fastapi import APIRouter
from pydantic import BaseModel
from app.core.world import WorldEngine

router = APIRouter()
world = WorldEngine()

class SetVarInput(BaseModel):
    key: str
    value: str

@router.post("/set")
def set_var(data: SetVarInput):
    world.set_var(data.key, data.value)
    return {"status": "ok", "world": world.export()}

@router.get("/state")
def get_state():
    return world.export()