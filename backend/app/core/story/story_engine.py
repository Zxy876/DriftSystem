# story/story_engine.py

from typing import Dict, List, Any


class StoryEngine:
    """
    一个极简的剧情引擎：
    - 用字典保存所有节点
    - current_node_id 表示当前进度
    - go_next(option_id) 根据选项推进
    """

    def __init__(self) -> None:
        # 昆明湖 第一章：从“被填的湖”开始
        self.nodes: Dict[str, Dict[str, Any]] = {
            "K1_START": {
                "id": "K1_START",
                "title": "昆明湖 · 序章：被动的孩子",
                "text": (
                    "“昆明转身湖水换成泪，我欲把心寄给春再暖一回。”\n\n"
                    "你站在一个正在被填的院子小湖边。\n"
                    "小时候的分别、老师匆匆一面、兴趣被终止，都像湖水被一点点填平。\n"
                    "你知道自己一直在被动地告别，但又说不出哪里不对。"
                ),
                "options": [
                    {"id": 0, "text": "静静看着父亲往湖里丢石头"},
                    {"id": 1, "text": "想要开口说点什么，却又犹豫"}
                ],
                "next": {
                    0: "K1_FILLING",
                    1: "K1_FILLING"
                }
            },

            "K1_FILLING": {
                "id": "K1_FILLING",
                "title": "填湖与教书先生",
                "text": (
                    "梦里，院子里的水太浅了。父亲听人说“深一点好”，开始往湖里填石头。\n"
                    "一边是巨石坠入水中的闷响，一边是教书先生滔滔不绝的说教。\n"
                    "你像个小工，被安排去完成这场“填湖工程”，却谁也没有问过你的感受。\n"
                    "每一块石头砸进湖水，像是砸在你心上——你很想哭。"
                ),
                "options": [
                    {"id": 0, "text": "继续埋头干活，不打断任何人"},
                    {"id": 1, "text": "在心里悄悄问一句：那我的湖呢？"}
                ],
                "next": {
                    0: "K1_DUCK",
                    1: "K1_DUCK"
                }
            },

            "K1_DUCK": {
                "id": "K1_DUCK",
                "title": "“填鸭”与私塾",
                "text": (
                    "后来，你做的梦几乎都变成了父亲的窘迫。\n"
                    "学校委婉地下了“转学令”，父亲却执拗地四处为你找“私塾”。\n\n"
                    "有人终于说出了那个词：你被“填鸭”了。\n"
                    "起初你很想为自己辩解——大家都是为你好，大家都在叫你“做自己”。\n"
                    "可是在辩解的过程中，你和她却达成了一个共识：\n"
                    "——原来，你的湖，一直在被别人决定要不要填。"
                ),
                "options": [
                    {"id": 0, "text": "点点头：那我到底想要什么？"},
                    {"id": 1, "text": "继续说服自己：也许他们都是对的"}
                ],
                "next": {
                    0: "K1_BREAKPOINT",
                    1: "K1_BREAKPOINT"
                }
            },

            "K1_BREAKPOINT": {
                "id": "K1_BREAKPOINT",
                "title": "半杯茶，半杯沙",
                "text": (
                    "某个时刻，你终于鼓起勇气，去回应所有人的期望。\n"
                    "你给他们倒了一杯茶：\n"
                    "——半杯是茶，半杯是填湖的沙。\n\n"
                    "你既在回应他们的好意，又想让人看见：\n"
                    "追寻“昆明”的那条路，并不轻松，也不是一句“加油就好”能概括的。"
                ),
                "options": [
                    {"id": 0, "text": "承认：我也想为了自己，留一片湖"},
                    {"id": 1, "text": "暂时什么都不说，只是把茶杯推过去"}
                ],
                "next": {
                    0: "K1_TEARS",
                    1: "K1_TEARS"
                }
            },

            "K1_TEARS": {
                "id": "K1_TEARS",
                "title": "只有昆明",
                "text": (
                    "传说，那杯本该给昆明的茶，一夜之间被倒向了北方某个“昆明湖”。\n"
                    "湖水的眼泪变成蒸汽，跟着云飞，最后又落回彩云之南。\n\n"
                    "你为自己取名“昆明”。\n"
                    "不是为了好听，而是为了提醒自己：\n"
                    "——从这里开始，不再只是“被填的湖”。\n"
                    "——从这里开始，只有昆明。"
                ),
                "options": [],
                "next": {}
            }
        }

        # 第一关起点
        self.current_node_id: str = "K1_START"

    # --------------- 对外接口 -----------------

    def get_current_node(self) -> Dict[str, Any]:
        """返回当前节点的完整信息"""
        node = self.nodes[self.current_node_id]
        # 深拷贝一份，避免被外部误改
        return {
            "id": node["id"],
            "title": node["title"],
            "text": node["text"],
            "options": list(node.get("options", []))
        }

    def go_next(self, option_id: int = 0) -> Dict[str, Any]:
        """
        根据选项推进：
        - 如果该节点没有 next 映射，就停在当前节点
        - 如果 option_id 不在 next 中，也停在当前节点
        """
        node = self.nodes[self.current_node_id]
        next_map = node.get("next", {})

        if not next_map:
            # 终点
            return self.get_current_node()

        target = next_map.get(option_id)
        if target is None:
            # 非法选项，保持不变
            return self.get_current_node()

        # 更新当前节点
        if target in self.nodes:
            self.current_node_id = target

        return self.get_current_node()