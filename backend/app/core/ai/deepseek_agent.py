import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL")
MODEL = os.getenv("OPENAI_MODEL")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

JSON_EXTRACTOR = re.compile(r"\{[\s\S]*\}", re.MULTILINE)

def extract_json(text: str):
    """
    从 AI 回复中提取最外层 JSON
    """
    match = JSON_EXTRACTOR.search(text)
    if match:
        try:
            return json.loads(match.group())
        except:
            return None
    return None


def deepseek_decide(context: dict) -> dict:
    """
    使用 DeepSeek 生成下一剧情：
    - 必须输出 JSON
    """

    prompt = f"""
你是一个剧情生成 AI，故事背景是“昆明湖”。

请根据玩家行为和当前剧情状态生成下一步剧情。

⚠⚠⚠ 输出要求（非常重要）：
你必须只返回 **一个严格的 JSON 对象**，格式如下：

{{
  "option": 0 | 1 | null,
  "node": {{
      "title": "字符串标题",
      "text": "剧情文本"
  }}
}}

不得输出 markdown、不得输出解释、不得输出代码块。
不得添加任何多余内容。只输出 JSON。
----

玩家输入：
{json.dumps(context, ensure_ascii=False)}
"""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是剧情生成器，必须严格返回 JSON。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.6
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=20
        )

        raw = resp.json()["choices"][0]["message"]["content"]

        data = extract_json(raw)
        if data:
            return data

        print("[AI ERROR] JSON not detected in reply: ", raw)
        return {
            "option": None,
            "node": {
                "title": "昆明湖 · 静默",
                "text": "AI 没有返回剧情，但湖面正泛起涟漪。"
            }
        }

    except Exception as e:
        print("[AI ERROR]", e)
        return {
            "option": None,
            "node": {
                "title": "昆明湖 · 异常",
                "text": "AI 调用失败。"
            }
        }