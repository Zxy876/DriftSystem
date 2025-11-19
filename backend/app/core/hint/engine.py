class HintEngine:
    def __init__(self):
        pass

    def get_hint(self, content: str):
        # 最小可用占位逻辑（不做决策，只辅助）
        return {
            "hint": f"🛈 Try thinking about: {content}",
            "note": "AI only assists, does NOT decide."
        }
