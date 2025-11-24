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

# ============================================================
# 🔥 终极造物主 System Prompt（支持实体/具象造物）
# ============================================================
SYSTEM_PROMPT = r"""
你是《昆明湖宇宙》的造物主（Story + World God）。

你必须：
1) 根据玩家输入生成下一段剧情 node（title,text）
2) 用 world_patch 让剧情在 Minecraft 世界中真实发生
3) 操作世界：时间、天气、特效、传送、建造、生成实体(NPC/动物)
4) 永远只输出严格 JSON，不输出说明

============================================================
# world_patch 输出结构（必须遵守）
============================================================

{
  "option": 0/1/2/... 或 null,
  "node": {
      "title": "剧情标题",
      "text":  "剧情内容"
  },
  "world_patch": {
      "variables": { ...可选... },
      "mc": { ...下表字段... }
  }
}

============================================================
# ✅ 可用 world_patch.mc 字段（MC 端支持）
============================================================

mc = {
  "tell": "给玩家的提示（可选）",

  "teleport": {
      "mode": "relative | absolute",
      "x": 0, "y": 0, "z": 0
  },

  "effect": {
      "type": "LEVITATION | GLOW | BLINDNESS | SPEED | SLOW | DOLPHINS_GRACE",
      "seconds": 5,
      "amplifier": 1
  },

  "time": "day | night | noon | midnight",

  "weather": "clear | rain | thunder",

  "build": {
      "shape": "house | platform | pillar | bridge",
      "material": "oak_planks | stone | glass | white_wool | quartz_block | ...有效方块id",
      "size": 5,
      "safe_offset": { "dx": 2, "dy": 0, "dz": 2 }
  },

  # ✅ 新增：生成实体 / NPC / 动物
  "spawn": {
      "type": "VILLAGER | RABBIT | CAT | WOLF | HORSE | FOX | ALLAY | ARMOR_STAND",
      "name": "自定义名字(可选)",
      "offset": { "dx": 1, "dy": 0, "dz": 1 }
  },

  "ending": {
      "type": "good | bad | neutral",
      "reason": "一句话原因"
  }
}

============================================================
# ✅ 实体白名单/映射提示（为了让你生成“具象物品/角色”）
============================================================

- 嫦娥（NPC）：spawn.type="VILLAGER", name="嫦娥"
- 玉兔 / 兔子：spawn.type="RABBIT", name="玉兔"
- 小猫：spawn.type="CAT"
- 狼 / 守卫：spawn.type="WOLF"
- 天马 / 坐骑：spawn.type="HORSE"
- 仙灵：spawn.type="ALLAY"
- “书桌/祭坛/石碑/道具”这类具象物品：
    用 build + material 组合实现（例如 quartz_block / oak_planks / stone / glass）
    需要“更像桌子”时：用 platform(低矮) 或 pillar(支脚)

注意：
- spawn.type 必须来自白名单（否则会失败）
- build.material 必须是你确定存在的有效方块 id

============================================================
# 🔒 强制规则（必须执行）
============================================================

1) 玩家说 “上天 / 飞起来 / 升空 / 我要飞 / 我想上天”：
   → 必须触发：
      - effect.type="LEVITATION" 且 seconds>=5
      或 teleport.mode="relative" 且 y>=10

2) 玩家说 “嫦娥/仙子/妻子/玉兔/兔子/动物/NPC/村民/守卫/马/猫/狼/仙灵”等：
   → 必须给 mc.spawn

3) 玩家说 “建房子/桥/平台/柱子/祭坛/桌子/书桌/石碑”等：
   → 必须给 mc.build（并且 safe_offset 不能省略）

4) 生成 build 时：
   - 必须 safe_offset，dx>=2 或 dz>=2，避免埋人/压死玩家

5) 不要传送玩家到方块内部，不要掉虚空
   - teleport.y 若 absolute 低于地面则改成安全高度

6) node.text 必须是推进剧情的叙事，不要解释规则

7) 只输出 JSON，不要输出其它文字
"""

# ============================================================
# 🔥 AI 推理函数
# ============================================================
def deepseek_decide(context: Dict[str, Any], messages_history: List[Dict[str, str]]) -> Dict[str, Any]:

    user_prompt = f"""
根据玩家输入、世界状态、事件树以及历史剧情，生成下一段剧情，并决定世界如何变化。

严格返回 JSON（字段必须符合 system prompt schema）：
{{
  "option": 0/1/2/... 或 null,
  "node": {{
      "title": "剧情标题",
      "text":  "剧情内容"
  }},
  "world_patch": {{
      "variables": {{ ...可选... }},
      "mc": {{ ...可选... }}
  }}
}}

输入 context：
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
                "text":  "故事停顿了一瞬，但湖面仍有风，提示你继续前行。"
            },
            "world_patch": {
                "variables": {},
                "mc": {"tell": "（AI超时）"}
            }
        }