from fastapi import APIRouter
import os, json

router = APIRouter()

LEVEL_DIR = "backend/data/heart_levels"

@router.post("/story/inject")
async def inject_story_level(level_id: str, title: str, text: str):

    filepath = f"{LEVEL_DIR}/{level_id}.json"

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

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {
        "status": "ok",
        "level_id": level_id,  # 返回level_id而不是path
        "path": filepath
    }