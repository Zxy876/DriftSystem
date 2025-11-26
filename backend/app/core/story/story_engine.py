# backend/app/core/story/story_engine.py

import time
from typing import Dict, Any, Tuple, List, Optional

from app.core.ai.deepseek_agent import deepseek_decide
from app.core.story.story_loader import load_level, build_level_prompt, Level


class StoryEngine:
    def __init__(self):
        self.players: Dict[str, Dict[str, Any]] = {}

        self.move_cooldown = 3.0
        self.say_cooldown = 0.8

        self.start_node_id = "START"
        self.current_node_id = "START"

        print(">>> StoryEngine initialized OK.")

    # -------------------- Player State --------------------
    def _ensure_player(self, player_id: str):
        """初始化玩家状态"""
        if player_id not in self.players:
            self.players[player_id] = {
                "messages": [],          # 对话消息记录
                "nodes": [],             # 触发的剧情节点
                "last_time": 0.0,
                "last_say_time": 0.0,
                "level": None,           # 当前 Level 对象
                "level_loaded": False,
                "tree_state": None,
                "ended": False
            }

    # -------------------- Load Level --------------------
    def load_level_for_player(self, player_id: str, level_id: str) -> Dict[str, Any]:
        """加载指定关卡"""
        self._ensure_player(player_id)
        level = load_level(level_id)

        p = self.players[player_id]
        p["level"] = level
        p["level_loaded"] = False
        p["tree_state"] = level.tree
        p["ended"] = False

        # 清空历史消息
        p["messages"].clear()
        p["nodes"].clear()

        return level.bootstrap_patch

    def _inject_level_prompt_if_needed(self, player_id: str):
        """首次加载关卡时注入提示 prompt"""
        p = self.players[player_id]
        level: Optional[Level] = p.get("level")

        if not level or p["level_loaded"]:
            return

        level_prompt = build_level_prompt(level)
        p["messages"].insert(0, {"role": "system", "content": level_prompt})
        p["level_loaded"] = True

    # -------------------- Message Helpers --------------------
    def _append_user_say(self, player_id: str, say: str):
        say = say.strip()
        if say:
            self.players[player_id]["messages"].append({"role": "user", "content": say})

    def _append_ai_node(self, player_id: str, node: Dict[str, Any]):
        title = node.get("title", "")
        text = node.get("text", "")
        self.players[player_id]["nodes"].append(node)

        self.players[player_id]["messages"].append({
            "role": "assistant",
            "content": f"{title}\n{text}".strip()
        })

        self.current_node_id = title or "UNKNOWN"

    # -------------------- Gating --------------------
    def should_advance(self, player_id: str, world_state: Dict[str, Any], action: Dict[str, Any]) -> bool:
        """控制说话和移动的节奏"""
        self._ensure_player(player_id)
        now = time.time()

        say = action.get("say")
        if isinstance(say, str) and say.strip():
            return (now - self.players[player_id]["last_say_time"]) >= self.say_cooldown

        last = self.players[player_id]["last_time"]
        if now - last < self.move_cooldown:
            return False

        move = action.get("move", {})
        return move.get("moving") is True and move.get("speed", 0) > 0.02

    # -------------------- FREE MODE HOOK --------------------
    def _ensure_free_mode_level(self, player_id: str):
        """
        如果玩家没有加载过任何关卡，
        自动进入「心悦自由宇宙模式」 heart_free。
        """
        p = self.players[player_id]

        if p["level"] is None:
            print(f"[StoryEngine] Player {player_id} entered FREE MODE.")

            class FreeLevel:
                level_id = "heart_free"
                tree = None
                bootstrap_patch = {
                    "mc": {
                        "tell": "🌌 进入心悦自由宇宙模式。在这里，你能用自然语言创造整个世界。"
                    }
                }

            p["level"] = FreeLevel()
            p["level_loaded"] = True  # 自由模式不需要 prompt 注入

    # -------------------- Main Advance --------------------
    def advance(
        self,
        player_id: str,
        world_state: Dict[str, Any],
        action: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[Dict[str, Any]], Dict[str, Any]]:

        self._ensure_player(player_id)
        p = self.players[player_id]

        # ========== ★ 若没有关卡则进入自由模式 ★ ==========
        self._ensure_free_mode_level(player_id)

        # ========== 注入关卡 prompt（如果是剧情关卡） ==========
        self._inject_level_prompt_if_needed(player_id)

        # ---------- ENDING ----------
        if p["ended"]:
            return None, None, {"mc": {"tell": "本关已结束，使用 /level <id> 开始下一关。"}}

        # ---------- SAY ----------
        say = action.get("say")
        if isinstance(say, str) and say.strip():
            self._append_user_say(player_id, say)

        messages = p["messages"]
        nodes = p["nodes"]

        ai_input = {
            "player_action": action,
            "world_state": world_state,
            "recent_nodes": nodes[-5:],
            "tree_state": p["tree_state"],
            "level_id": p["level"].level_id,
        }

        ai_result = deepseek_decide(ai_input, messages)

        option = ai_result.get("option")
        node = ai_result.get("node")
        patch = ai_result.get("world_patch", {}) or {}
        mc_patch = patch.get("mc", {}) or {}

        # ---------- 树状态 ----------
        if option is not None:
            p["tree_state"] = {
                "last_option": option,
                "ts": time.time(),
            }

        # ---------- AI Node ----------
        if node:
            self._append_ai_node(player_id, node)

        # ---------- Ending Hook ----------
        if mc_patch.get("ending"):
            p["ended"] = True
            ending = mc_patch["ending"]
            etype = ending.get("type", "neutral")

            if etype == "good":
                mc_patch.setdefault("tell", "【GOOD END】宇宙为你打开了一扇新的门。")
                mc_patch.setdefault("teleport", {"mode": "relative", "x": 0, "y": 10, "z": 0})

            elif etype == "bad":
                mc_patch.setdefault("tell", "【BAD END】光被世界收走。")
                mc_patch.setdefault("effect", {"type": "WITHER", "seconds": 5, "amplifier": 2})

            patch["mc"] = mc_patch

        # ---------- Update Time ----------
        now = time.time()
        if isinstance(say, str) and say.strip():
            p["last_say_time"] = now
        else:
            p["last_time"] = now

        return option, node, patch

    # -------------------- Public APIs --------------------
    def get_public_state(self, player_id: Optional[str] = None):
        if player_id:
            self._ensure_player(player_id)
            p = self.players[player_id]
            return {
                "player_id": player_id,
                "history_len": len(p["nodes"]),
                "level": p["level"].level_id if p["level"] else None,
                "last_node": p["nodes"][-1] if p["nodes"] else None
            }

        return {
            "start_node": self.start_node_id,
            "current_node": self.current_node_id,
            "players": {
                pid: {
                    "history_len": len(data["nodes"]),
                    "level": data["level"].level_id if data["level"] else None,
                    "last_node": data["nodes"][-1] if data["nodes"] else None
                }
                for pid, data in self.players.items()
            }
        }

    def get_history(self, player_id: str):
        self._ensure_player(player_id)
        return self.players[player_id]["nodes"]

    def clear_history(self, player_id: str):
        self._ensure_player(player_id)
        p = self.players[player_id]

        p["nodes"].clear()
        p["messages"].clear()
        p["last_time"] = 0.0
        p["last_say_time"] = 0.0
        p["ended"] = False
        p["level_loaded"] = False


story_engine = StoryEngine()