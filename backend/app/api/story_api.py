# backend/app/api/story_api.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import os
import json

from app.core.story.story_loader import (
    list_levels,
    load_level,
    DATA_DIR,          # ⭐ 使用 story_loader 的同一个目录
)
from app.core.story.story_engine import story_engine

router = APIRouter(prefix="/story")

# ============================================================
# ✔ Pydantic 模型（用于 JSON 注入）
# ============================================================
class InjectPayload(BaseModel):
    level_id: str     # test_inject
    title: str        # 测试剧情
    text: str         # 单段剧情文本（自动转成 list）


# ============================================================
# ✔ 获取所有关卡
# ============================================================
@router.get("/levels")
def api_story_levels():
    return {"status": "ok", "levels": list_levels()}


# ============================================================
# ✔ 获取关卡详情
# ============================================================
@router.get("/level/{level_id}")
def api_story_level(level_id: str):
    try:
        lv = load_level(level_id)
        return {"status": "ok", "level": lv.__dict__}
    except FileNotFoundError:
        return {"status": "error", "msg": f"Level {level_id} not found"}


# ============================================================
# ✔ 加载关卡（Minecraft 进入剧情）
# ============================================================
@router.post("/load/{player_id}/{level_id}")
def api_story_load(player_id: str, level_id: str):
    try:
        patch = story_engine.load_level_for_player(player_id, level_id)
        return {"status": "ok", "msg": f"{level_id} loaded", "bootstrap_patch": patch}
    except FileNotFoundError:
        return {"status": "error", "msg": f"Level {level_id} not found"}


# ============================================================
# ✔ 推进剧情
# ============================================================
@router.post("/advance/{player_id}")
def api_story_advance(player_id: str, payload: Dict[str, Any]):
    world_state = payload.get("world_state", {}) or {}
    action = payload.get("action", {}) or {}

    option, node, patch = story_engine.advance(player_id, world_state, action)
    return {
        "status": "ok",
        "option": option,
        "node": node,
        "world_patch": patch
    }


# ============================================================
# ✔ 获取玩家当前 Story 状态
# ============================================================
@router.get("/state/{player_id}")
def api_story_state(player_id: str):
    return {"status": "ok", "state": story_engine.get_public_state(player_id)}


# ============================================================
# ⭐ NEW：创建新的剧情关卡（以 JSON Body 注入）
# ============================================================
@router.post("/inject")
def api_story_inject(payload: InjectPayload):
    """
    JSON Body 示例：
    {
        "level_id": "test_inject",
        "title": "测试剧情",
        "text": "这是自动注入的剧情节点"
    }
    """
    LEVEL_DIR = DATA_DIR                         # ⭐ 与 story_loader 使用相同目录
    os.makedirs(LEVEL_DIR, exist_ok=True)

    file_path = os.path.join(LEVEL_DIR, f"{payload.level_id}.json")

    if os.path.exists(file_path):
        raise HTTPException(
            status_code=400,
            detail=f"Level {payload.level_id} already exists"
        )

    # ⭐ 使用AI生成完整的世界内容（NPC、环境、建筑等）
    from app.core.ai.deepseek_agent import call_deepseek
    
    ai_prompt = f"""
基于用户的故事描述生成一个完整的Minecraft世界场景。
用户描述：{payload.text}

要求：
1. 生成spawn点（玩家出生位置）
2. 生成至少1-3个NPC（类型从villager/zombie/skeleton/cow/pig选择）
3. 生成环境建筑（使用简单方块如stone/oak_planks/glass等）
4. 设置天气和时间（如晴天/白天，或雨天/夜晚营造氛围）

返回JSON格式：
{{
  "spawn": {{"x": 0, "y": 70, "z": 0}},
  "npcs": [
    {{"type": "villager", "name": "商人", "x": 5, "y": 70, "z": 0, "dialog": "欢迎光临！"}},
    {{"type": "cow", "name": "奶牛", "x": -3, "y": 70, "z": 2}}
  ],
  "blocks": [
    {{"type": "stone", "x": 0, "y": 69, "z": 0}},
    {{"type": "oak_planks", "x": 1, "y": 70, "z": 1}}
  ],
  "time": "day",
  "weather": "clear"
}}
"""
    
    try:
        ai_result = call_deepseek(
            context={"type": "world_generation", "story": payload.text},
            messages=[{"role": "user", "content": ai_prompt}],
            temperature=0.8
        )
        
        # 解析AI返回的世界数据
        world_data = json.loads(ai_result.get("response", "{}"))
        
        # 构造bootstrap_patch包含AI生成的完整世界
        bootstrap_patch = {
            "variables": {
                "story_world_generated": True,
                "story_title": payload.title
            },
            "mc": {
                "tell": f"§6{payload.title}§r\n{payload.text}",
                "spawn": world_data.get("spawn", {"x": 0, "y": 70, "z": 0}),
                "time": world_data.get("time", "day"),
                "weather": world_data.get("weather", "clear")
            }
        }
        
        # 添加NPC生成指令
        npcs_data = world_data.get("npcs", [])
        if npcs_data:
            bootstrap_patch["mc"]["spawns"] = [
                {
                    "type": npc.get("type", "villager"),
                    "name": npc.get("name", "NPC"),
                    "x": npc.get("x", 0),
                    "y": npc.get("y", 70),
                    "z": npc.get("z", 0),
                    "dialog": npc.get("dialog", "")
                }
                for npc in npcs_data
            ]
        
        # 添加建筑方块（简化处理）
        blocks_data = world_data.get("blocks", [])
        if blocks_data:
            bootstrap_patch["mc"]["blocks"] = blocks_data[:50]  # 限制数量避免卡顿
            
    except Exception as e:
        # AI调用失败时回退到基础版本
        print(f"AI world generation failed: {e}")
        bootstrap_patch = {
            "variables": {},
            "mc": {
                "tell": f"§6{payload.title}§r\n{payload.text}",
                "spawn": {"x": 0, "y": 70, "z": 0}
            }
        }

    # ⭐ 生成兼容 Level 类的结构（全部字段完整）
    data = {
        "id": payload.level_id,
        "title": payload.title,
        "text": [payload.text],                 # ⭐ 必须为 list[str]
        "tags": [],
        "mood": {"base": "calm", "intensity": 0.5},
        "choices": [],
        "meta": {},
        "npcs": [],
        "bootstrap_patch": bootstrap_patch,
        "tree": None
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {
        "status": "ok",
        "msg": f"Level {payload.level_id} created with AI-generated world",
        "file": file_path,
        "world_preview": bootstrap_patch.get("mc", {})
    }