



# backend/app/core/story/engine.py

class StoryEngine:
    def __init__(self):
        self.current_node_id = "K1_START"

        # ======= 剧情树 =======
        self.tree = {
            "K1_START": {
                "id": "K1_START",
                "title": "昆明湖 · 序章：被动的孩子",
                "text": "你站在正在被填平的小湖边，耳边只有铁锹落下的声音。",
                "options": [
                    {"id": 0, "text": "静静看着父亲往湖里丢石头"},
                    {"id": 1, "text": "想开口说点什么，却又犹豫"}
                ]
            },

            "A0_NEXT": {
                "id": "A0_NEXT",
                "title": "碎石落湖",
                "text": "石头溅起的水花像是被强行终止的某段童年。",
                "options": [
                    {"id": 0, "text": "继续沉默"},
                    {"id": 1, "text": "试图阻止父亲"}
                ]
            },

            "B0_NEXT": {
                "id": "B0_NEXT",
                "title": "未说出口的话",
                "text": "你张了张嘴，但喉咙像被湖水灌满一样。",
                "options": [
                    {"id": 0, "text": "鼓起勇气开口"},
                    {"id": 1, "text": "还是算了"}
                ]
            },
        }

    # 获取当前节点
    def get_current_node(self):
        return self.tree.get(self.current_node_id, None)

    # 推进剧情
    def go_next(self, option_id: int):
        if option_id == 0:
            next_id = "A0_NEXT"
        elif option_id == 1:
            next_id = "B0_NEXT"
        else:
            next_id = "K1_START"

        self.current_node_id = next_id
        return self.tree[next_id]
