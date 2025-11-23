import os, json, requests
from dotenv import load_dotenv
from typing import List, Dict, Any

load_dotenv()

API_KEY  = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL    = os.getenv("OPENAI_MODEL", "deepseek-chat")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def deepseek_decide(context: Dict[str, Any], messages_history: List[Dict[str, str]]) -> Dict[str, Any]:
    system = (
        "你是昆明湖场景的剧情生成器 + 世界导演。"
        "你必须只返回合法 JSON，不得输出任何解释或多余文本。"
        "剧情要承接历史内容，保持连贯推进。"
        "你可以通过 world_patch 改变世界。"
        "world_patch.variables 用于后端世界变量，world_patch.mc 用于MC表现。"
    )

    user_prompt = f"""
根据玩家状态、行动和历史剧情，生成下一段连贯剧情，并给出世界修改指令。

严格返回 JSON：
{{
  "option": 0 或 1 或 null,
  "node": {{
      "title": "字符串",
      "text": "字符串"
  }},
  "world_patch": {{
      "variables": {{ ...可选... }},
      "mc": {{
          "tell": "给玩家的一句话(可选)",
          "teleport": {{"dx":0,"dy":0,"dz":0}} (可选),
          "effect": {{"type":"SLOW|BLINDNESS|GLOW","seconds":5,"amplifier":1}} (可选)
      }}
  }}
}}

当前输入：
{json.dumps(context, ensure_ascii=False)}
"""

    messages = [{"role": "system", "content": system}]
    messages += messages_history[-12:]
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=40
        )
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
        return json.loads(raw)

    except Exception as e:
        print("[AI ERROR]", e)
        return {
            "option": None,
            "node": {
                "title": "昆明湖 · 静默",
                "text": "AI 沉默了一瞬，但湖面的风仍提醒你：故事没有断。"
            },
            "world_patch": {"variables": {}, "mc": {"tell": "（AI超时）"}}
        }