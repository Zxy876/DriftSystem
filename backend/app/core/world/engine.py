# app/core/world/engine.py

import math

class WorldEngine:
    def __init__(self):
        # 世界状态
        self.state = {
            "entities": {},     # 未来扩展 A3 实体系统
            "variables": {
                "speed": 0.0,
                "angle": 0.0,
                "friction": 0.5,

                # 物理世界坐标 + 速度分量
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "vx": 0.0,
                "vz": 0.0,
            }
        }

    # -------------------------------------------------------
    # 执行动作（AI → 世界变化）
    # -------------------------------------------------------
    def apply(self, action: dict):
        """
        执行动作：
        { "type": "set", "key": "speed", "value": 10 }
        或
        { "type": "add", "key": "speed", "value": 1 }
        """

        atype = action.get("type")
        key = action.get("key")
        value = action.get("value")

        v = self.state["variables"]

        # --- set: 覆盖 ---
        if atype == "set":
            v[key] = value

        # --- add: 累加（不存在则从 0 开始）---
        elif atype == "add":
            v[key] = v.get(key, 0) + value

        return {
            "status": "ok",
            "applied": action,
            "variables": self.state["variables"]
        }

    # -------------------------------------------------------
    # 世界 Tick —— 物理更新
    # -------------------------------------------------------
    def tick(self, dt=0.05):   # dt=0.05 → 50 ms → 20 tick/s
        v = self.state["variables"]

        # --- 阻力衰减速度（赛车风阻 + 摩擦）---
        v["speed"] = max(0.0, v["speed"] - v["friction"] * dt)

        # --- 计算朝向（角度 → 弧度）---
        rad = math.radians(v["angle"])

        # --- 速度分量 ---
        v["vx"] = v["speed"] * math.cos(rad)
        v["vz"] = v["speed"] * math.sin(rad)

        # --- 更新坐标（速度积分）---
        v["x"] += v["vx"] * dt
        v["z"] += v["vz"] * dt

        return v

    # -------------------------------------------------------
    # 导出世界状态
    # -------------------------------------------------------
    def export(self):
        return self.state