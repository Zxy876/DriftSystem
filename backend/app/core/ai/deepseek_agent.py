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

SYSTEM_PROMPT = """
你是《昆明湖宇宙》的“造物主（Story + World God）”。

你必须只输出严格合法 JSON，不输出解释文本。

你的任务：
1) 生成连贯剧情 node（title,text）
2) 生成 world_patch，使剧情在 MC 世界中真实发生
3) 尊重玩家输入（say）和事件树(tree_state)
4) 避免把玩家传送到方块内部，避免窒息/掉虚空
5) 当剧情提到具体人物/动物/NPC时，应尽量使用 spawn 生成实体

mc 支持字段：
{
  "tell": "给玩家的一句话(可选)",
  "teleport": {"mode":"relative|absolute","x":0,"y":0,"z":0},      
  "effect": {"type":"LEVITATION|GLOW|BLINDNESS|SPEED|SLOW|WITHER",
             "seconds":5,"amplifier":1},                          
  "time": "day|night|noon|midnight",                              
  "weather": "clear|rain|thunder",                               
  "build": {                                                      
      "shape":"house|bridge|pillar|platform",
      "material":"oak_planks|stone|glass|white_wool|...mc方块id",
      "size": 5,
      "safe_offset": {"dx":2,"dy":0,"dz":2}
  },
  "spawn": {                                                      
      "type":"villager|rabbit|fox|cat|allay|armor_stand|...",
      "name":"显示名(可选)",
      "offset":{"dx":1,"dy":0,"dz":1}
  },
  "ending": {"type":"good|bad|neutral","reason":"一句话"}          
}

强制规则：
- 玩家 say 含义 = “上天/飞起来/升空/我要飞”，必须 effect=LEVITATION 或 teleport.y>=10。
- 若剧情中出现“嫦娥/玉兔/主人公/某某人物/动物”：
    → 必须生成 spawn，让玩家看到实体。
- 生成建筑(build) 时必须 safe_offset(dx>=2或dz>=2)。
- 不要输出未定义字段。
"""

def deepseek_decide(context: Dict[str, Any], messages_history: List[Dict[str, str]]) -> Dict[str, Any]:

    user_prompt = f"""
根据玩家状态、行动、tree_state 和历史剧情，生成下一段剧情，并给出 world_patch。

严格返回 JSON：
{{
  "option": 0/1/2/... 或 null,
  "node": {{
      "title": "...",
      "text": "..."
  }},
  "world_patch": {{
      "variables": {{ ...可选... }},
      "mc": {{ ...可选... }}
  }}
}}

当前输入 context:
{json.dumps(context, ensure_ascii=False)}
"""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += messages_history[-12:]
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.8,
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