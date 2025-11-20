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
        if not model:
            raise ValueError("❌ OPENAI_MODEL 未设置")

        self.model = model

        # 初始化 openai 客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

    def get_hint(self, content: str):
        state = self.tree_engine.export_state()
        current = state["current"]

        prompt = (
            f"当前节点：{current}\n"
            f"用户输入：{content}\n"
            f"请给一个推理建议，不要替用户做决策。"
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # ⭐ 正确的取内容方式
            msg = resp.choices[0].message.content

        except Exception as e:
            msg = f"AI 调用失败：{e}"

        return {
            "input": content,
            "current_node": current,
            "suggestion": msg,
            "meta": "AI reasoning assistant"
        }