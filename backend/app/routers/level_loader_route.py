from fastapi import APIRouter
from app.core.story.level_loader import load_level, build_level_prompt
from app.core.story.story_engine import story_engine

router = APIRouter()

@router.post("/story/load_level")
def load_level_api(player_id: str, level_id: str):
    lv = load_level(level_id)

    prompt = build_level_prompt(lv)

    story_engine.clear_history(player_id)
    story_engine.players[player_id]["messages"].append({
        "role": "system",
        "content": prompt
    })

    return {
        "status": "ok",
        "level": level_id,
        "title": lv.title
    }
