# backend/app/routers/ai_router.py
import requests
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

DEEPSEEK_API_KEY = "sk-361935fad03540238c8c3e6c36e79ee6"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


# ----------- 输入格式 ----------- 
class AiInput(BaseModel):
    player_id: str
    message: str
    world_state: dict | None = None


# ----------- DeepSeek 调用 ----------- 
def call_deepseek(message: str) -> dict:
    """
    你想要的心悦宇宙 LLM 事件推理器：
    输入一句自然语言 → 输出 DSL + 回复
    """

    system_prompt = """
你是“心悦宇宙 AI 事件推理器”。

你的任务：
1. 理解玩家自然语言意图（中文/混合语言）
2. 输出两个字段：
   reply：自然语言反馈、温柔、鼓励、氛围感十足
   dsl：MC 世界脚本（只给机器看的）

DSL 语法由你决定，允许：
- 世界变化命令（set time night / day / rain / clear）
- 玩家动作（tp player x y z）
- 心悦文集剧情推进（story next / story load 关卡）
- 氛围 UI（title "xxx" / actionbar "xxx"）
- AI 评论（say "..."）
- 世界事件（spawn npc / fog / world shift）
- 自定义心悦宇宙事件（ceremony_start, lake_shift）

你必须输出严格 JSON：
{
  "reply": "...",
  "dsl": "..."
}

如果不能理解就输出：
{
  "reply": "我听到了，但我需要更具体一点。",
  "dsl": ""
}
"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": message}
        ],
        "temperature": 0.4
    }

    try:
        r = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=15)
        data = r.json()
        text = data["choices"][0]["message"]["content"]

        # DeepSeek 输出的 content 本身就是 JSON 字符串
        import json
        return json.loads(text)

    except Exception as e:
        return {
            "reply": f"我暂时断开了连接：{e}",
            "dsl": ""
        }


# ----------- FastAPI 路由： MC 插件调用这里 -----------
@router.post("/route/{player_id}")
def ai_route(player_id: str, data: AiInput):

    result = call_deepseek(data.message)

    return {
        "status": "ok",
        "player_id": player_id,
        "reply": result.get("reply", ""),
        "dsl": result.get("dsl", "")
    }