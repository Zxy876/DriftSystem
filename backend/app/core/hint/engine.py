import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class HintEngine:
    def __init__(self, tree_engine):
        self.tree_engine = tree_engine
        
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        model = os.getenv("OPENAI_MODEL")

        if not api_key:
            raise ValueError("❌ OPENAI_API_KEY 未设置")
        if not base_url:
            raise ValueError("❌ OPENAI_BASE_URL 未设置")

        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _safe_json(self, text: str):
        """尝试将模型输出解析为 JSON，如果失败则原样返回"""
        try:
            return json.loads(text)
        except:
            return {"raw": text}

    def get_hint(self, content: str):
        state = self.tree_engine.export_state()
        current = state["current"]

        prompt = f"""
你是一个推理引擎，只返回合法 JSON，不允许出现 markdown 代码块。

结构要求：

{{
  "summary": "对用户输入的总结",
  "reasoning": "给一个推理方向，但不要替用户做决定",
  "action": null   // 未来用于世界操控
}}

规则：
- 不要使用 ```json
- 不要使用自然语言解释
- 只能返回 JSON（没有其他字符）

用户输入：{content}
当前节点：{current}
"""

        # --- 调用 API ---
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3  # 稳定输出结构
            )
            raw_msg = resp.choices[0].message.content

            parsed = self._safe_json(raw_msg)

            return {
                "input": content,
                "current_node": current,
                "result": parsed,
                "meta": "AI reasoning assistant"
            }

        except Exception as e:
            return {
                "input": content,
                "current_node": current,
                "result": None,
                "error": str(e),
                "meta": "AI reasoning assistant"
            }