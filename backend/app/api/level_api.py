from fastapi import APIRouter
import json
from pathlib import Path

from app.core.story.story_loader import DATA_DIR

router = APIRouter()

LEVEL_DIR = Path(DATA_DIR)

@router.post("/story/inject")
async def inject_story_level(level_id: str, title: str, text: str):

    LEVEL_DIR.mkdir(parents=True, exist_ok=True)

    target_id = level_id.strip()
    if target_id.endswith(".json"):
        target_id = target_id[:-5]
    lower_id = target_id.lower()
    if not lower_id.startswith("flagship_"):
        if lower_id.startswith("level_"):
            suffix = target_id.split("_", 1)[1]
            target_id = f"flagship_{suffix}"
        else:
            target_id = f"flagship_{target_id}"

    filepath = LEVEL_DIR / f"{target_id}.json"

    # 为新关卡创建一个独特的场景配置
    data = {
        "title": title,
        "text": text,
        "options": [],
        "world_patch": {
            "mc": {
                "spawn": {
                    "type": "villager",
                    "name": "剧情NPC",
                    "offset": {"dx": 3, "dy": 0, "dz": 3}
                },
                "build": {
                    "shape": "platform",
                    "size": 5,
                    "material": "stone"
                },
                "tell": f"✨ 欢迎来到【{title}】"
            }
        }
    }

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {
        "status": "ok",
        "level_id": target_id,
        "path": str(filepath)
    }