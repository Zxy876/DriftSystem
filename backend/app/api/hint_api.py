from fastapi import APIRouter
from pydantic import BaseModel
from app.core.hint.engine import HintEngine

router = APIRouter()
engine = HintEngine()

class HintInput(BaseModel):
    content: str

@router.post("/")
def hint(data: HintInput):
    return engine.get_hint(data.content)