from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.world.engine import WorldEngine
from app.core.story.manager import story_engine
from app.core.ai.deepseek_agent import deepseek_decide


router = APIRouter()

world = WorldEngine()


# -------------------------
# 输入数据模型
# -------------------------
class WorldAction(BaseModel):
    action: dict


# -------------------------
# 获取世界状态
# -------------------------
@router.get("/state")
def get_state():
    return JSONResponse(content=world.export())


# -------------------------
# 处理 MC 玩家行为
# -------------------------
@router.post("/apply")
def apply_action(req: WorldAction):

    # 1. 先更新世界（可选）
    world_result = world.apply(req.action)

    # DeepSeek 输入上下文 —— 简化且统一
    context = {
        "player_action": req.action.get("move", {}),
        "variables": world_result["variables"],  # 这是关键
        "current_story_node": story_engine.current_node_id
    }

    # 2. 让 DeepSeek 决策
    ai_result = deepseek_decide(context)

    # ai_result 结构：
    # {
    #   "option": 0 或 1 或 null,
    #   "node": { "title": "...", "text": "..." }
    # }

    option = ai_result.get("option", None)
    node = ai_result.get("node", None)

    final_story = None

    # -------------------------
    # Case A：玩家行为触发 DeepSeek 给出 option（剧情推进）
    # -------------------------
    if option is not None:
        final_story = story_engine.go_next(option)

    # -------------------------
    # Case B：DeepSeek 生成独立剧情 node（无需触发 option）
    # 例如：AI 给了 {"node": {...}} 你那条“湖边的微风”
    # -------------------------
    elif node is not None:
        final_story = node

    # -------------------------
    # Case C：完全没剧情
    # -------------------------
    else:
        final_story = None

    return JSONResponse(content={
        "status": "ok",
        "world_state": world_result,
        "ai_option": option,
        "story_node": final_story
    })
