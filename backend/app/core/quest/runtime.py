"""Quest runtime for Stage 3 quest and task handling."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from app.core.story.story_loader import Level
from app.core.story.level_schema import RuleListener


class QuestRuntime:
    """In-memory quest runtime coordinating per-player task state."""

    def __init__(self) -> None:
        self._players: Dict[str, Dict[str, Any]] = {}
        self._phase3_announced = False
        self._rule_listeners: List[RuleListener] = []

    # ------------------------------------------------------------------
    # Phase 1.5 scaffolding
    # ------------------------------------------------------------------
    def register_rule_listener(self, listener: Optional[RuleListener]) -> None:
        """Register a rule listener for future bridge wiring."""

        if listener is None or not getattr(listener, "type", None):
            return

        self._rule_listeners.append(listener)
        # TODO: emit to RuleEventBridge once implemented.

    def handle_rule_trigger(self, player_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle an incoming rule trigger (stub)."""

        state = self._players.get(player_id)
        if not state:
            return None

        state.setdefault("rule_events", []).append(payload)
        # TODO: apply payload to active tasks based on TaskEventType.
        return None

    def evaluate_exit_conditions(self, player_id: str) -> Optional[Dict[str, Any]]:
        """Return exit readiness snapshot for the player (stub)."""

        state = self._players.get(player_id)
        if not state:
            return None

        if self._all_tasks_completed(state):
            return {"exit_ready": True}

        # TODO: incorporate exit phrases and milestones from ExitConfig.
        return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def load_level_tasks(self, level: Level, player_id: str) -> None:
        tasks = [self._normalize_task(raw, index) for index, raw in enumerate(level.tasks or [])]
        state = {
            "level_id": level.level_id,
            "level_title": level.title,
            "level": level,
            "tasks": tasks,
            "issued_index": -1,
            "completed_count": 0,
            "summary_emitted": False,
            "last_completed_type": None,
        }
        self._players[player_id] = state

    def exit_level(self, player_id: str) -> None:
        self._players.pop(player_id, None)

    # ------------------------------------------------------------------
    # Event ingestion and beat coordination
    # ------------------------------------------------------------------
    def record_event(self, player_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        state = self._players.get(player_id)
        if not state:
            return None

        task = self._find_active_task(state)
        if not task:
            return None

        normalized_event = self._normalize_event(event)
        if not normalized_event:
            return None

        state["last_event"] = normalized_event

        if not self._event_matches(task, normalized_event):
            return None

        progress = task.setdefault("progress", 0) + 1
        task["progress"] = progress
        required = task.get("count", 1)
        task.setdefault("history", []).append({
            "event": normalized_event.get("event_type"),
            "target": normalized_event.get("target"),
            "meta": normalized_event.get("meta", {}),
            "ts": time.time(),
        })

        if progress < required:
            remaining = max(0, required - progress)
            return {"matched": True, "remaining": remaining}

        task["status"] = "completed"
        return {
            "completed": True,
            "task_id": task["id"],
        }

    def issue_tasks_on_beat(
        self,
        level_or_id: Union[Level, str],
        player_id: str,
        beat: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        level = self._extract_level(level_or_id, player_id)
        if not level:
            return None

        state = self._ensure_state(player_id, level)
        if not state:
            return None

        issued = self._issue_next_task(state, level, beat or {})
        if not issued:
            return None

        return {
            "nodes": [issued],
        }

    def check_completion(self, level_or_id: Union[Level, str], player_id: str) -> Optional[Dict[str, Any]]:
        level = self._extract_level(level_or_id, player_id)
        if not level:
            return None

        state = self._ensure_state(player_id, level)
        if not state:
            return None

        updates: Dict[str, Any] = {
            "nodes": [],
            "world_patch": {},
            "completed_tasks": [],
        }

        rewards = self._collect_rewards(state, level)
        if rewards:
            updates["world_patch"] = self._merge_patch(updates["world_patch"], rewards.get("world_patch"))
            updates["nodes"].extend(rewards.get("nodes", []))
            updates["completed_tasks"].extend(rewards.get("completed_tasks", []))

        if self._all_tasks_completed(state) and not state.get("summary_emitted"):
            summary = self._build_summary_node(level, state)
            updates["nodes"].append(summary)
            updates["summary"] = summary
            state["summary_emitted"] = True
            updates["exit_ready"] = True

            if not self._phase3_announced and state.get("last_completed_type") == "kill":
                print("Phase 3 complete, proceed to Phase 4")
                self._phase3_announced = True

        if (
            not updates["nodes"]
            and not updates["world_patch"]
            and not updates.get("completed_tasks")
            and not updates.get("exit_ready")
        ):
            return None

        return updates

    # ------------------------------------------------------------------
    # Task coordination helpers
    # ------------------------------------------------------------------
    def assign_dynamic_task(self, player_id: str, task_def: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        state = self._players.get(player_id)
        if not state:
            return None
        task = self._normalize_task(task_def, len(state["tasks"]))
        state["tasks"].append(task)
        return task

    def get_runtime_snapshot(self, player_id: str) -> Dict[str, Any]:
        state = self._players.get(player_id, {})
        return {
            "level_id": state.get("level_id"),
            "exit_ready": bool(state.get("summary_emitted")),
            "tasks": [
                {
                    "id": task.get("id"),
                    "status": task.get("status"),
                    "progress": task.get("progress", 0),
                    "count": task.get("count", 1),
                }
                for task in state.get("tasks", [])
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_state(self, player_id: str, level: Optional[Level] = None) -> Optional[Dict[str, Any]]:
        state = self._players.get(player_id)
        if level is None:
            return state

        if not state or state.get("level_id") != level.level_id:
            self.load_level_tasks(level, player_id)
            state = self._players.get(player_id)

        return state

    def _normalize_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(event, dict):
            return None

        event_type = event.get("event_type") or event.get("type")
        target = event.get("target") or event.get("target_id")
        meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}

        if not isinstance(event_type, str) or not event_type:
            return None

        normalized = {
            "event_type": event_type.lower(),
            "target": target,
            "meta": meta,
        }

        if event.get("count") is not None:
            normalized["count"] = event.get("count")

        return normalized
    # ------------------------------------------------------------------
    def _normalize_task(self, task: Dict[str, Any], index: int) -> Dict[str, Any]:
        if not isinstance(task, dict):
            task = {}
        task_id = str(task.get("id") or f"task_{index:02d}")
        task_type = str(task.get("type") or "custom").lower()
        target = task.get("target") or {}
        count = task.get("count") or 1
        reward = task.get("reward") or {}
        dialogue = task.get("dialogue") or {}

        normalized = {
            "id": task_id,
            "type": task_type,
            "target": target,
            "count": max(1, int(count)),
            "reward": reward,
            "dialogue": dialogue,
            "status": "pending",
        }
        normalized["history"] = []
        issue_node = task.get("issue_node")
        if isinstance(issue_node, dict):
            normalized["issue_node"] = issue_node
        return normalized

    def _issue_next_task(self, state: Dict[str, Any], level: Level, beat: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        tasks = state.get("tasks", [])
        for task in tasks:
            if task.get("status") == "pending":
                task["status"] = "issued"
                task.setdefault("progress", 0)
                task.setdefault("history", []).append({
                    "event": "issued",
                    "beat": beat.get("id"),
                    "ts": time.time(),
                })
                state["issued_index"] = tasks.index(task)
                return self._build_issue_node(level, task)
        return None

    def _collect_rewards(self, state: Dict[str, Any], level: Level) -> Optional[Dict[str, Any]]:
        world_patch: Dict[str, Any] = {}
        nodes: List[Dict[str, Any]] = []
        completed: List[str] = []
        for task in state.get("tasks", []):
            if task.get("status") == "completed" and not task.get("rewarded"):
                reward = task.get("reward") or {}
                world_patch = self._merge_patch(world_patch, reward.get("world_patch"))
                if "npc_dialogue" in reward:
                    world_patch = self._merge_patch(world_patch, {"npc_dialogue": reward["npc_dialogue"]})
                nodes.append(self._build_reward_node(level, task))
                task["rewarded"] = True
                state["completed_count"] += 1
                state["last_completed_type"] = task.get("type")
                completed.append(task.get("id"))
        if not nodes and not world_patch:
            return None
        return {
            "world_patch": world_patch,
            "nodes": nodes,
            "completed_tasks": completed,
        }

    def _all_tasks_completed(self, state: Dict[str, Any]) -> bool:
        tasks = state.get("tasks", [])
        return bool(tasks) and all(task.get("status") == "completed" for task in tasks)

    def _build_issue_node(self, level: Level, task: Dict[str, Any]) -> Dict[str, Any]:
        node = task.get("issue_node") or {}
        title = node.get("title") or f"任务：{task['id']}"
        text = node.get("text") or self._default_issue_text(task)
        return {
            "title": title,
            "text": text,
            "type": "task",
            "task_id": task["id"],
        }

    def _build_reward_node(self, level: Level, task: Dict[str, Any]) -> Dict[str, Any]:
        text = task.get("dialogue", {}).get("on_complete") or "任务完成，奖励已发放。"
        return {
            "title": f"完成：{task['id']}",
            "text": text,
            "type": "task_complete",
            "task_id": task["id"],
        }

    def _build_summary_node(self, level: Level, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": f"{level.title} · 任务总结",
            "text": "全部任务已完成，你可以随时返回昆明湖。",
            "type": "task_summary",
        }

    def _default_issue_text(self, task: Dict[str, Any]) -> str:
        task_type = task.get("type")
        target = task.get("target")
        count = task.get("count", 1)
        if isinstance(target, dict):
            name = target.get("name") or target.get("type")
        else:
            name = str(target)
        return f"请完成目标（{task_type}:{name}） x{count}."

    def _find_active_task(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for task in state.get("tasks", []):
            if task.get("status") == "issued":
                return task
        return None

    def _event_matches(self, task: Dict[str, Any], event: Dict[str, Any]) -> bool:
        expected_type = task.get("type")
        if event.get("event_type") != expected_type:
            return False

        target = task.get("target")
        event_target = event.get("target")
        if not target or not event_target:
            return True

        if isinstance(target, str):
            return str(event_target).lower() == target.lower()

        if isinstance(target, dict):
            target_name = str(target.get("name") or target.get("type") or "").lower()
            return target_name == str(event_target).lower()

        return False

    @staticmethod
    def _merge_patch(base: Optional[Dict[str, Any]], addition: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not addition:
            return dict(base or {})
        merged = dict(base or {})
        for key, value in addition.items():
            if key == "mc" and isinstance(value, dict):
                existing = merged.get("mc")
                if isinstance(existing, dict):
                    merged["mc"] = {**existing, **value}
                else:
                    merged["mc"] = dict(value)
            else:
                merged[key] = value
        return merged


quest_runtime = QuestRuntime()


class TaskEventType(Enum):
    """Event types emitted by the Minecraft rule bridge."""

    BLOCK_BREAK = "BLOCK_BREAK"
    ENTITY_KILL = "ENTITY_KILL"
    ITEM_COLLECT = "ITEM_COLLECT"
    AREA_REACH = "AREA_REACH"
    DIALOGUE = "DIALOGUE"
