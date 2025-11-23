import math
import uuid

class WorldEngine:
    def __init__(self):
        # 世界状态
        self.state = {
            "entities": {},     # id -> {type, x,y,z, other_info}
            "variables": {
                "speed": 0.0,
                "angle": 0.0,
                "friction": 0.5,

                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "vx": 0.0,
                "vz": 0.0,
            }
        }

    # =====================================================
    # 物理变量更新（你的赛车世界）
    # =====================================================
    def apply(self, action: dict):
        atype = action.get("type")
        key = action.get("key")
        value = action.get("value")

        v = self.state["variables"]

        if atype == "set":
            v[key] = value

        elif atype == "add":
            v[key] = v.get(key, 0) + value

        return {
            "status": "ok",
            "applied": action,
            "variables": self.state["variables"]
        }

    # =====================================================
    # 允许 AI 修改世界（造物主核心）
    # =====================================================
    def apply_patch(self, patch: dict):
        """
        patch 格式：
        {
            "variables": { ... },         # 覆盖变量
            "entities": {
                "create": [{...}],        # 创建实体
                "update": [{...}],        # 修改实体
                "delete": ["id1","id2"],  # 删除实体
            },
            "mc": { ... }                 # 发送给 MC 插件的命令
        }
        """
        # ----------- 更新 variables ----------
        if "variables" in patch:
            for k, v in patch["variables"].items():
                self.state["variables"][k] = v

        # ----------- 处理实体 --------------
        entities = self.state["entities"]

        ent_patch = patch.get("entities", {})

        # create
        for obj in ent_patch.get("create", []):
            obj_id = obj.get("id", str(uuid.uuid4())[:8])
            entities[obj_id] = obj

        # update
        for obj in ent_patch.get("update", []):
            obj_id = obj["id"]
            if obj_id in entities:
                entities[obj_id].update(obj)

        # delete
        for obj_id in ent_patch.get("delete", []):
            entities.pop(obj_id, None)

        # 最终返回世界状态 + 供 MC 执行的指令
        return {
            "status": "ok",
            "variables": self.state["variables"],
            "entities": self.state["entities"],
            "mc": patch.get("mc")
        }

    def get_state(self):
        return self.state