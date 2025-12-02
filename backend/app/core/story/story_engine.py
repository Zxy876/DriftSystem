# backend/app/core/story/story_engine.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.core.ai.deepseek_agent import deepseek_decide
from app.core.story.story_loader import load_level, build_level_prompt, Level
from app.core.story.story_graph import StoryGraph
from app.core.world.minimap import MiniMap
from app.core.world.scene_generator import SceneGenerator
from app.core.world.trigger import trigger_engine
from app.core.world.trigger import TriggerPoint


class StoryEngine:
    def __init__(self):
        self.players: Dict[str, Dict[str, Any]] = {}

        self.move_cooldown = 3.0
        self.say_cooldown = 0.8

        base_dir = Path(__file__).resolve().parents[3]
        level_dir = base_dir / "data" / "heart_levels"

        self.graph = StoryGraph(str(level_dir))
        self.minimap = MiniMap(self.graph)
        self.scene_gen = SceneGenerator()

        self._inject_spiral_triggers()

        print(
            f"[StoryEngine] loaded {len(self.graph.all_levels())} levels "
            f"from {level_dir}"
        )

    # ------------------- 状态 -------------------
    def get_public_state(self, player_id: Optional[str] = None):
        return {
            "total_levels": len(self.graph.all_levels()),
            "levels": sorted(list(self.graph.all_levels())),
            "players": list(self.players.keys()),
            "player_current_level": (
                self.players.get(player_id, {}).get("level").level_id
                if player_id in self.players and self.players[player_id].get("level")
                else None
            ),
        }

    def _ensure_player(self, player_id: str):
        if player_id not in self.players:
            self.players[player_id] = {
                "messages": [],
                "nodes": [],
                "level": None,
                "level_loaded": False,
                "tree_state": None,
                "ended": False,
                "last_time": 0.0,
                "last_say_time": 0.0,
            }

    # ------------------- 关卡逻辑 -------------------
    def get_next_level_id(self, current_level_id: Optional[str]):
        if not current_level_id or not current_level_id.startswith("level_"):
            all_levels = sorted(self.graph.all_levels())
            return "level_01" if "level_01" in all_levels else all_levels[0]
        return self.graph.bfs_next(current_level_id)

    def load_next_level_for_player(self, player_id: str) -> Dict[str, Any]:
        self._ensure_player(player_id)
        p = self.players[player_id]
        current_level = getattr(p["level"], "level_id", None)
        next_id = self.get_next_level_id(current_level)
        if not next_id:
            p["ended"] = True
            return {"mc": {"tell": "🎉 已经是最后一关了。"}}
        return self.load_level_for_player(player_id, next_id)

    def load_level_for_player(self, player_id: str, level_id: str) -> Dict[str, Any]:
        """
        加载指定关卡 + 生成场景 patch（平台/NPC/建筑等）
        """
        self._ensure_player(player_id)
        level: Level = load_level(level_id)
        p = self.players[player_id]

        p["level"] = level
        p["level_loaded"] = False
        p["tree_state"] = level.tree
        p["ended"] = False
        p["messages"].clear()
        p["nodes"].clear()

        # minimap：进度记录 + 点亮节点
        self.minimap.enter_level(player_id, level_id)
        self.minimap.mark_unlocked(player_id, level_id)

        scene_patch = self.scene_gen.generate_for_level(level_id, level.__dict__)

        base_patch = dict(level.bootstrap_patch or {})
        base_mc = dict(base_patch.get("mc") or {})
        scene_mc = dict((scene_patch or {}).get("mc") or {})
        base_mc.update(scene_mc)
        base_patch["mc"] = base_mc

        return base_patch

    # ------------------- prompt 注入 -------------------
    def _inject_level_prompt_if_needed(self, player_id: str):
        p = self.players[player_id]
        level = p["level"]
        if not level or p["level_loaded"]:
            return
        p["messages"].insert(
            0, {"role": "system", "content": build_level_prompt(level)}
        )
        p["level_loaded"] = True

    # ------------------- 触发区 -------------------
    def _inject_spiral_triggers(self):
        trigger_engine.triggers.clear()
        BASE_X = 200
        BASE_Z = 200
        SCALE = 12

        for lv in self.graph.all_levels():
            pos = self.minimap.positions.get(lv)
            if not pos:
                continue

            world_x = BASE_X + pos["x"] * SCALE
            world_z = BASE_Z + pos["y"] * SCALE

            trigger_engine.triggers.append(
                TriggerPoint(
                    id=f"trigger_{lv}",
                    center=(world_x, 70, world_z),
                    radius=4.0,
                    action="load_level",
                    level_id=lv,
                )
            )
        print(f"[Trigger] spiral triggers = {len(trigger_engine.triggers)}")

    # ------------------- 冷却判断（/world/apply 用） -------------------
    def should_advance(self, player_id: str, world_state: Dict[str, Any], action: Dict[str, Any]) -> bool:
        self._ensure_player(player_id)
        now = time.time()
        p = self.players[player_id]

        say = action.get("say")
        if isinstance(say, str) and say.strip():
            if now - p["last_say_time"] >= self.say_cooldown:
                p["last_say_time"] = now
                return True
            return False

        last = p["last_time"]
        if now - last < self.move_cooldown:
            return False

        p["last_time"] = now
        return True

    # ------------------- 主推进 -------------------
    def advance(
        self, player_id: str, world_state: Dict[str, Any], action: Dict[str, Any]
    ) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
        self._ensure_player(player_id)
        p = self.players[player_id]

        self._ensure_free_mode_level(player_id)
        self._inject_level_prompt_if_needed(player_id)

        if p["ended"]:
            return None, None, {"mc": {"tell": "本关已结束。"}}

        say = action.get("say")
        if isinstance(say, str) and say.strip():
            p["messages"].append({"role": "user", "content": say})

        vars_ = world_state.get("variables") or {}
        x, y, z = vars_.get("x", 0.0), vars_.get("y", 0.0), vars_.get("z", 0.0)
        self.minimap.update_player_pos(player_id, (x, y, z))

        trg = trigger_engine.check(player_id, x, y, z)
        if trg and trg.action == "load_level" and trg.level_id:
            patch = self.load_level_for_player(player_id, trg.level_id)
            node = {
                "title": "世界触发点",
                "text": f"你抵达了关键地点，关卡 {trg.level_id} 被唤醒。",
            }
            return None, node, patch

        ai_input = {
            "player_id": player_id,
            "player_action": action,
            "world_state": world_state,
            "recent_nodes": p["nodes"][-5:],
            "tree_state": p["tree_state"],
            "level_id": p["level"].level_id,
        }

        ai_result = deepseek_decide(ai_input, p["messages"])

        option = ai_result.get("option")
        node = ai_result.get("node")
        patch = ai_result.get("world_patch", {}) or {}
        mc_patch = patch.get("mc", {}) or {}

        if option is not None:
            p["tree_state"] = {"last_option": option, "ts": time.time()}

        if node:
            p["nodes"].append(node)
            p["messages"].append(
                {
                    "role": "assistant",
                    "content": f"{node.get('title','')}\n{node.get('text','')}".strip(),
                }
            )
            cur_level = p["level"].level_id
            self.minimap.mark_unlocked(player_id, cur_level)

        if mc_patch.get("ending"):
            p["ended"] = True

        now = time.time()
        if say and say.strip():
            p["last_say_time"] = now
        else:
            p["last_time"] = now

        return option, node, patch

    # ------------------- 自由模式 -------------------
    def _ensure_free_mode_level(self, player_id: str):
        p = self.players[player_id]
        if p["level"] is None:

            class FreeLevel:
                level_id = "heart_free"
                tree = None
                bootstrap_patch = {"mc": {"tell": "🌌 进入心悦自由宇宙模式。"}}

            p["level"] = FreeLevel()
            p["level_loaded"] = True


story_engine = StoryEngine()