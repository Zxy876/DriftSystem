import time, re
from typing import Dict, Any, Tuple, List, Optional

from app.core.ai.deepseek_agent import deepseek_decide

# 事件树可选：如果你已有 tree_engine，就自动接入；没有也能跑
try:
    from app.core.tree.engine import tree_engine  # 你自己的 tree 引擎
except Exception:
    tree_engine = None


class StoryEngine:
    """
    L4 造物主引擎：
    - move / say 推进
    - 无限生成（没有预设终点，也可由 AI 给 ending）
    - 事件树 options 介入（玩家可 /choose N）
    - patch 成为真实世界变化
    """

    def __init__(self):
        self.players: Dict[str, Dict[str, Any]] = {}

        self.move_cooldown = 2.0
        self.say_cooldown  = 0.5

        self.start_node_id = "START"
        self.current_node_id = "START"

        print(">>> StoryEngine L4 initialized OK.")

    # ---------------- internal ----------------
    def _ensure_player(self, player_id: str):
        if player_id not in self.players:
            self.players[player_id] = {
                "messages": [],
                "nodes": [],
                "last_time": 0.0,
                "last_say_time": 0.0,
                "ending": None,          # 记录结局
                "tree_node": "START",    # 当前事件树节点
            }

    def _append_user_say(self, player_id: str, say: str):
        self._ensure_player(player_id)
        say = say.strip()
        if not say:
            return
        self.players[player_id]["messages"].append({
            "role": "user",
            "content": say
        })

    def _append_ai_node(self, player_id: str, node: Dict[str, Any]):
        self._ensure_player(player_id)
        title = node.get("title", "")
        text  = node.get("text", "")
        self.players[player_id]["nodes"].append(node)
        self.players[player_id]["messages"].append({
            "role": "assistant",
            "content": f"{title}\n{text}".strip()
        })
        self.current_node_id = title or "UNKNOWN"

    def _parse_choice(self, say: str) -> Optional[int]:
        """
        玩家可以在 chat 里用：
        /choose 1
        选择事件树分支
        """
        m = re.search(r"/choose\s+(\d+)", say.strip().lower())
        if m:
            return int(m.group(1))
        return None

    def _get_tree_options(self, player_id: str) -> List[str]:
        if not tree_engine:
            return []
        node_id = self.players[player_id]["tree_node"]
        try:
            return tree_engine.get_options(node_id)  # 你 tree_engine 的接口
        except Exception:
            return []

    # ---------------- rhythm ----------------
    def should_advance(
        self,
        player_id: str,
        world_state: Dict[str, Any],
        action: Dict[str, Any]
    ) -> bool:
        self._ensure_player(player_id)
        now = time.time()

        say = action.get("say")
        if isinstance(say, str) and say.strip():
            last_say = self.players[player_id]["last_say_time"]
            return (now - last_say) >= self.say_cooldown

        last = self.players[player_id]["last_time"]
        if now - last < self.move_cooldown:
            return False

        move = action.get("move", {})
        return move.get("moving") is True and move.get("speed", 0) > 0.02

    # ---------------- advance ----------------
    def advance(
        self,
        player_id: str,
        world_state: Dict[str, Any],
        action: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[Dict[str, Any]], Dict[str, Any]]:

        self._ensure_player(player_id)

        say = action.get("say", "")
        if isinstance(say, str) and say.strip():
            self._append_user_say(player_id, say)

        # === 玩家显式选择事件树分支 ===
        forced_option = None
        if isinstance(say, str):
            forced_option = self._parse_choice(say)

        options = self._get_tree_options(player_id)

        messages: List[Dict[str, str]] = self.players[player_id]["messages"]
        nodes: List[Dict[str, Any]] = self.players[player_id]["nodes"]

        ai_input = {
            "player_action": action,
            "world_state": world_state,
            "recent_nodes": nodes[-5:],
            "tree": {
                "current": self.players[player_id]["tree_node"],
                "options": options
            },
            "forced_option": forced_option
        }

        ai_result = deepseek_decide(ai_input, messages)

        option = forced_option if forced_option is not None else ai_result.get("option", None)
        node   = ai_result.get("node", None)
        patch  = ai_result.get("world_patch", {}) or {}

        # === 更新事件树节点 ===
        if tree_engine and option is not None and isinstance(option, int):
            try:
                new_tree_node = tree_engine.apply_choice(
                    self.players[player_id]["tree_node"], option
                )
                self.players[player_id]["tree_node"] = new_tree_node
            except Exception:
                pass

        # === 强制“上天”规则（不靠 AI 随机）===
        if isinstance(say, str) and re.search(r"上天|飞起来|升空|我要飞", say):
            patch.setdefault("mc", {})
            patch["mc"].setdefault("tell", "你脚下的重力被解除，身体轻轻上升。")
            patch["mc"]["effect"] = {"type": "LEVITATION", "seconds": 6, "amplifier": 1}

        # === AI 结局记录（决定生死/传送）===
        ending = patch.get("mc", {}).get("ending")
        if ending:
            self.players[player_id]["ending"] = ending

        if node:
            self._append_ai_node(player_id, node)

        now = time.time()
        if isinstance(say, str) and say.strip():
            self.players[player_id]["last_say_time"] = now
        else:
            self.players[player_id]["last_time"] = now

        return option, node, patch

    # ---------------- public api ----------------
    def get_public_state(self, player_id: Optional[str] = None):
        if player_id:
            self._ensure_player(player_id)
            p = self.players[player_id]
            return {
                "player_id": player_id,
                "history_len": len(p["nodes"]),
                "last_node": p["nodes"][-1] if p["nodes"] else None,
                "ending": p["ending"],
                "tree_node": p["tree_node"],
                "tree_options": self._get_tree_options(player_id)
            }

        return {
            "start_node": self.start_node_id,
            "current_node": self.current_node_id,
            "players": {
                pid: {
                    "history_len": len(data["nodes"]),
                    "last_node": data["nodes"][-1] if data["nodes"] else None,
                    "ending": data["ending"],
                    "tree_node": data["tree_node"]
                }
                for pid, data in self.players.items()
            }
        }

    def get_history(self, player_id: str):
        self._ensure_player(player_id)
        return self.players[player_id]["nodes"]

    def clear_history(self, player_id: str):
        self._ensure_player(player_id)
        self.players[player_id]["nodes"].clear()
        self.players[player_id]["messages"].clear()
        self.players[player_id]["last_time"] = 0.0
        self.players[player_id]["last_say_time"] = 0.0
        self.players[player_id]["ending"] = None
        self.players[player_id]["tree_node"] = "START"


story_engine = StoryEngine()