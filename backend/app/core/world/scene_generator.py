# backend/app/core/world/scene_generator.py
from __future__ import annotations
from typing import Dict, Any

"""
SceneGenerator —— 根据关卡内容自动生成 MC 世界环境 patch
"""


class SceneGenerator:

    def generate_for_level(self, level_id: str, level_data: dict) -> Dict[str, Any]:
        title = level_data.get("title", "")
        text_list = level_data.get("text", [])
        text = "\n".join(text_list)

        # ---- 主模板选择 ----
        if "飘移" in title or "漂移" in text:
            return self._scene_drift_track(level_id)

        if "隧道" in text or "回溯" in text:
            return self._scene_tunnel(level_id)

        if "考试" in text or "试卷" in text:
            return self._scene_exam_space(level_id)

        # 默认：心悦虚空场景
        return self._scene_void(level_id)

    # =========================
    # 具体模板
    # =========================

    def _scene_drift_track(self, level_id):
        """
        漂移关卡：生成赛道 + 平台 + NPC 桃子
        """
        return {
            "mc": {
                "teleport": {"mode": "absolute", "x": 0, "y": 70, "z": 0},
                "build": {
                    "shape": "circle",
                    "radius": 20,
                    "material": "gray_concrete"
                },
                "spawn": {
                    "type": "villager",
                    "name": "桃子",
                    "offset": {"dx": 2, "dy": 0, "dz": 2}
                },
                "title": f"§b【{level_id}】漂移赛道已加载",
            }
        }

    def _scene_tunnel(self, level_id):
        """
        隧道关卡
        """
        return {
            "mc": {
                "teleport": {"mode": "absolute", "x": 0, "y": 50, "z": 0},
                "build": {
                    "shape": "tunnel",
                    "length": 40,
                    "material": "stone_bricks"
                },
                "effect": {"type": "DARKNESS", "seconds": 3},
                "title": f"§8你进入隧道：{level_id}",
            }
        }

    def _scene_exam_space(self, level_id):
        """
        试卷世界 = 白色房间 + 光平台
        """
        return {
            "mc": {
                "teleport": {"mode": "absolute", "x": 0, "y": 100, "z": 0},
                "build": {
                    "shape": "cube",
                    "size": 30,
                    "material": "white_concrete"
                },
                "title": f"§f思考空间：{level_id}",
            }
        }

    def _scene_void(self, level_id):
        """
        默认虚空 + 安全平台
        """
        return {
            "mc": {
                "teleport": {"mode": "absolute", "x": 0, "y": 70, "z": 0},
                "build": {
                    "shape": "platform",
                    "size": 10,
                    "material": "quartz_block"
                },
                "title": f"§d虚空空间：{level_id}"
            }
        }