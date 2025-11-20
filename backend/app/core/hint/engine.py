import os
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

    def get_hint(self, content: str):
        state = self.tree_engine.export_state()
        current = state["current"]

        prompt = f"""
你是一个推理引擎，**只能返回 JSON，不能讲任何自然语言**。

返回结构为：

{{
  "summary": "对用户输入的简短总结",
  "reasoning": "推理方向，不替用户行动",
  "action": {{
      "type": "<动作类型或 'none'>",
      "args": {{}}
  }}
}}

动作类型示例（仅示例，不强制）：
- "none" → 不执行动作
- "ui.highlightNode"
- "system.updateContext"
- "dsl.compile"
- "dsl.execute"
- "minecraft.move"
- "minecraft.build"

严格返回 JSON，不要加注释，不要加代码块。

用户输入：{content}
当前节点：{current}
"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            msg = resp.choices[0].message.content
        except Exception as e:
            msg = f"AI 调用失败：{e}"

        return {
            "input": content,
            "current_node": current,
            "result": msg,
            "meta": "AI reasoning assistant"
        }