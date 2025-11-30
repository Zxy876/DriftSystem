# backend/app/routers/world.py
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.story.story_engine import story_engine

router = APIRouter(prefix="/world", tags=["world"])


class ApplyReq(BaseModel):
    player_id: str
    action: Dict[str, Any]
    world_state: Dict[str, Any] = {}


@router.post("/apply")
def apply(req: ApplyReq):
    """
    DriftSystem · 心悦宇宙
    主世界驱动入口：
    - MC 插件把玩家行为 + 世界状态 POST 到这里
    - 后端 StoryEngine 判定是否需要推进剧情 + 调 DeepSeek
    """
    player_id = req.player_id
    action = req.action or {}
    world_state = req.world_state or {}

    say = action.get("say", "")

    # ---------- 关卡命令：/level XXX ----------
    if isinstance(say, str) and say.strip().startswith("/level"):
        parts = say.strip().split()
        if len(parts) >= 2:
            level_suffix = parts[1]
            level_id = f"level_{level_suffix}" if not level_suffix.startswith("level_") else level_suffix

            patch = story_engine.load_level_for_player(player_id, level_id)

            return {
                "status": "ok",
                "story_node": {
                    "title": "关卡加载",
                    "text": f"已加载关卡 {level_id}，你听见世界开始呼吸。",
                },
                "world_patch": patch,
                "ai_option": None,
                "world_state": story_engine.get_public_state(player_id),
            }

        # 用法错误
        return {
            "status": "ok",
            "story_node": {
                "title": "关卡加载失败",
                "text": "用法：/level 01  或  /level 001",
            },
            "world_patch": {
                "mc": {"tell": "用法：/level 01  或  /level 001"},
            },
            "ai_option": None,
            "world_state": story_engine.get_public_state(player_id),
        }

    # ---------- 正常 AI 推进 ----------
    if not story_engine.should_advance(player_id, world_state, action):
        # 不触发 AI（冷却 / 玩家还在原地等）
        return {
            "status": "ok",
            "world_patch": {},
            "story_node": None,
            "ai_option": None,
            "world_state": story_engine.get_public_state(player_id),
        }

    option, node, patch = story_engine.advance(player_id, world_state, action)

    return {
        "status": "ok",
        "ai_option": option,
        "story_node": node,
        "world_patch": patch,
        "world_state": story_engine.get_public_state(player_id),
    }


@router.get("/state/{player_id}")
def get_state(player_id: str):
    """
    调试用：查看某个玩家在 StoryEngine 里的状态。
    """
    return story_engine.get_public_state(player_id)
