from fastapi import APIRouter
from pydantic import BaseModel
from app.core.tree.engine import TreeEngine

router = APIRouter()
engine = TreeEngine()

class NodeInput(BaseModel):
    content: str

@router.get("/state")
def get_state():
    return engine.export_state()

@router.post("/add")
def add_node(data: NodeInput):
    return engine.add(data.content)

@router.post("/backtrack")
def backtrack():
    return engine.backtrack()

@router.post("/breakpoint")
def breakpoint():
    return engine.breakpoint()