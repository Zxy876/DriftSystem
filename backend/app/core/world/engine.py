class WorldEngine:
    """
    世界状态管理器：
    - 存储世界对象（玩家、方块、UI 组件、变量等）
    - 支持 action 修改世界
    """

    def __init__(self):
        self.state = {
            "entities": {},
            "variables": {}
        }

    # 添加实体
    def add_entity(self, name, info):
        self.state["entities"][name] = info

    # 更新实体
    def update_entity(self, name, info):
        if name in self.state["entities"]:
            self.state["entities"][name].update(info)

    # 设置变量
    def set_var(self, key, value):
        self.state["variables"][key] = value

    # 导出世界状态（给给前端）
    def export(self):
        return self.state