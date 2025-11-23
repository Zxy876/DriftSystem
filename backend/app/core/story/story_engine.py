import time
from typing import Dict, Any, Tuple, List, Optional

from app.core.ai.deepseek_agent import deepseek_decide


class StoryEngine:
    def __init__(self):
        self.players: Dict[str, Dict[str, Any]] = {}

        self.move_cooldown = 3.0
        self.say_cooldown  = 0.8

        self.start_node_id = "START"
        self.current_node_id = "START"

        print(">>> StoryEngine initialized OK.")

    def _ensure_player(self, player_id: str):
        if player_id not in self.players:
            self.players[player_id] = {
                "messages": [],
                "nodes": [],
                "last_time": 0.0,
                "last_say_time": 0.0
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

    def should_advance(self, player_id: str, world_state: Dict[str, Any], action: Dict[str, Any]) -> bool:
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

    # ✅ 现在 advance 返回 (option, node, world_patch)
    def advance(
        self,
        player_id: str,
        world_state: Dict[str, Any],
        action: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[Dict[str, Any]], Dict[str, Any]]:

        self._ensure_player(player_id)

        say = action.get("say")
        if isinstance(say, str) and say.strip():
            self._append_user_say(player_id, say)

        messages: List[Dict[str, str]] = self.players[player_id]["messages"]
        nodes: List[Dict[str, Any]] = self.players[player_id]["nodes"]

        ai_input = {
            "player_action": action,
            "world_state": world_state,
            "recent_nodes": nodes[-5:],
        }

        ai_result = deepseek_decide(ai_input, messages)

        option = ai_result.get("option", None)
        node   = ai_result.get("node", None)
        patch  = ai_result.get("world_patch", {}) or {}

        if node:
            self._append_ai_node(player_id, node)

        now = time.time()
        if isinstance(say, str) and say.strip():
            self.players[player_id]["last_say_time"] = now
        else:
            self.players[player_id]["last_time"] = now

        return option, node, patch

    def get_public_state(self, player_id: Optional[str] = None):
        if player_id:
            self._ensure_player(player_id)
            p = self.players[player_id]
            return {
                "player_id": player_id,
                "history_len": len(p["nodes"]),
                "last_node": p["nodes"][-1] if p["nodes"] else None
            }

        return {
            "start_node": self.start_node_id,
            "current_node": self.current_node_id,
            "players": {
                pid: {
                    "history_len": len(data["nodes"]),
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
        self.players[player_id]["nodes"].clear()
        self.players[player_id]["messages"].clear()
        self.players[player_id]["last_time"] = 0.0
        self.players[player_id]["last_say_time"] = 0.0


story_engine = StoryEngine()