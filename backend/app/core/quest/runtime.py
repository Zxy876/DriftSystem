"""Quest runtime for Stage 3 quest and task handling."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union

from app.core.story.story_loader import Level
from app.core.story.level_schema import RuleListener
from app.core.npc import npc_engine


@dataclass
class TaskMilestone:
    """Intermediate checkpoints for a task."""

    id: str
    title: Optional[str] = None
    hint: Optional[str] = None
    target: Optional[str] = None
    count: int = 1
    progress: int = 0
    status: str = "pending"
    history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TaskSession:
    """Runtime container for a single task and its milestones."""

    id: str
    type: str
    target: Any
    title: str = ""
    hint: Optional[str] = None
    count: int = 1
    reward: Dict[str, Any] = field(default_factory=dict)
    dialogue: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    milestones: List[TaskMilestone] = field(default_factory=list)
    progress: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    rule_refs: List[str] = field(default_factory=list)

    def mark_issued(self, beat_id: Optional[str]) -> Dict[str, Any]:
        self.status = "issued"
        entry = {"event": "issued", "beat": beat_id, "ts": time.time()}
        self.history.append(entry)
        return entry

    def record_event(self, event: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Update task progress with an incoming normalized event."""

        if self.status != "issued":
            return False, None

        matched, milestone = self._match_event(event)
        if not matched:
            return False, None

        self.progress += 1
        self.history.append({"event": event, "ts": time.time()})

        milestone_payload: Optional[Dict[str, Any]] = None
        if milestone:
            milestone.history.append({"event": event, "ts": time.time()})
            milestone.progress += 1
            if milestone.progress >= milestone.count:
                milestone.status = "completed"
                milestone_payload = {
                    "milestone_completed": True,
                    "milestone_id": milestone.id,
                    "task_id": self.id,
                    "task_title": self.title,
                    "task_hint": self.hint,
                    "milestone_title": milestone.title,
                    "milestone_hint": milestone.hint,
                    "milestone_count": milestone.count,
                    "milestone_progress": milestone.progress,
                }

        if self.progress >= self.count:
            if not self.milestones or all(m.status == "completed" for m in self.milestones):
                self.status = "completed"
                return True, self._completion_payload()

        if milestone_payload is not None:
            milestone_payload.setdefault("task_progress", self.progress)
            milestone_payload.setdefault("task_count", self.count)

        return True, milestone_payload

    def _match_event(self, event: Dict[str, Any]) -> Tuple[bool, Optional[TaskMilestone]]:
        if not event:
            return False, None
        if event.get("event_type") != self.type:
            return False, None

        target = event.get("target")
        if self.target and target:
            if isinstance(self.target, str):
                if str(target).lower() != self.target.lower():
                    return False, None
            elif isinstance(self.target, dict):
                expected = str(self.target.get("name") or self.target.get("type") or "").lower()
                if expected and str(target).lower() != expected:
                    return False, None

        for milestone in self.milestones:
            if milestone.status == "completed":
                continue
            if milestone.target and target:
                if str(target).lower() != str(milestone.target).lower():
                    continue
            return True, milestone

        return True, None

    def _completion_payload(self) -> Dict[str, Any]:
        return {
            "task_completed": True,
            "task_id": self.id,
            "task_title": self.title,
            "task_hint": self.hint,
            "task_progress": self.progress,
            "task_count": self.count,
            "reward": self.reward,
            "dialogue": self.dialogue,
        }


class QuestRuntime:
    """In-memory quest runtime coordinating per-player task state."""

    def __init__(self) -> None:
        self._players: Dict[str, Dict[str, Any]] = {}
        self._phase3_announced = False
        self._rule_listeners: List[Tuple[str, RuleListener]] = []
        self._rule_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None

    # ------------------------------------------------------------------
    # Phase 1.5 scaffolding
    # ------------------------------------------------------------------
    def register_rule_listener(self, level_id: str, listener: Optional[RuleListener]) -> None:
        """Register a rule listener for future bridge wiring."""

        if listener is None or not getattr(listener, "type", None):
            return

        self._rule_listeners.append((level_id, listener))
        npc_engine.register_rule_binding(level_id, listener)

    def set_rule_callback(self, callback: Optional[Callable[[str, Dict[str, Any]], None]]) -> None:
        """Allow StoryEngine to observe rule triggers."""

        self._rule_callback = callback

    def handle_rule_trigger(self, player_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle an incoming rule trigger and advance relevant tasks."""

        state = self._players.get(player_id)
        if not state:
            return None

        normalized = self._normalize_event(payload)
        if not normalized:
            return None

        state.setdefault("rule_events", []).append(normalized)

        responses: List[Dict[str, Any]] = []
        for session in self._iter_active_sessions(state):
            matched, result = session.record_event(normalized)
            if not matched:
                continue
            if result:
                responses.append(result)
            remaining = max(0, session.count - session.progress)
            if remaining and session.status == "issued":
                responses.append({
                    "matched": True,
                    "remaining": remaining,
                    "task_id": session.id,
                    "task_title": session.title,
                    "task_hint": session.hint,
                    "task_progress": session.progress,
                    "task_count": session.count,
                })

        npc_payload = None
        level_id = state.get("level_id")
        if level_id:
            npc_payload = npc_engine.apply_rule_trigger(level_id, normalized, state.get("active_rule_refs", set()))

        combined = self._aggregate_rule_responses(state, responses)
        combined = self._merge_response_payload(combined, npc_payload)

        if self._rule_callback:
            try:
                self._rule_callback(player_id, payload)
            except Exception:
                pass

        return combined or None

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
        tasks = [self._create_session(raw, index) for index, raw in enumerate(level.tasks or [])]
        state = {
            "level_id": level.level_id,
            "level_title": level.title,
            "level": level,
            "tasks": tasks,
            "issued_index": -1,
            "completed_count": 0,
            "summary_emitted": False,
            "last_completed_type": None,
            "active_rule_refs": set(),
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

        normalized_event = self._normalize_event(event)
        if not normalized_event:
            return None

        state["last_event"] = normalized_event
        responses: List[Dict[str, Any]] = []
        for session in self._iter_active_sessions(state):
            matched, result = session.record_event(normalized_event)
            if matched:
                if result:
                    responses.append(result)
                remaining = max(0, session.count - session.progress)
                if remaining and session.status == "issued":
                    responses.append({
                        "matched": True,
                        "remaining": remaining,
                        "task_id": session.id,
                        "task_title": session.title,
                        "task_hint": session.hint,
                        "task_progress": session.progress,
                        "task_count": session.count,
                    })

        return self._aggregate_rule_responses(state, responses)

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

    def activate_rule_refs(
        self,
        level_or_id: Union[Level, str],
        player_id: str,
        rule_refs: Optional[List[str]] = None,
    ) -> None:
        if not rule_refs:
            return

        level = self._extract_level(level_or_id, player_id)
        if not level:
            return

        state = self._ensure_state(player_id, level)
        if not state:
            return

        active = state.setdefault("active_rule_refs", set())
        active.update(rule_refs)

        for session in self._iter_sessions(state):
            if not session.rule_refs:
                continue
            if any(ref in rule_refs for ref in session.rule_refs):
                session.history.append({
                    "event": "rule_ref_activated",
                    "refs": list(rule_refs),
                    "ts": time.time(),
                })

        npc_engine.activate_rule_refs(level.level_id, rule_refs)

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
        session = self._create_session(task_def, len(state["tasks"]))
        state["tasks"].append(session)
        return {
            "id": session.id,
            "type": session.type,
            "status": session.status,
            "count": session.count,
        }

    def get_runtime_snapshot(self, player_id: str) -> Dict[str, Any]:
        state = self._players.get(player_id, {})
        return {
            "level_id": state.get("level_id"),
            "exit_ready": bool(state.get("summary_emitted")),
            "tasks": [
                {
                    "id": session.id,
                    "title": session.title,
                    "hint": session.hint,
                    "status": session.status,
                    "progress": session.progress,
                    "count": session.count,
                }
                for session in state.get("tasks", [])
            ],
            "active_rule_refs": sorted(list(state.get("active_rule_refs", []))),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _extract_level(self, level_or_id: Union[Level, str], player_id: str) -> Optional[Level]:
        if isinstance(level_or_id, Level):
            return level_or_id

        if isinstance(level_or_id, str):
            state = self._players.get(player_id)
            level = state.get("level") if state else None
            if isinstance(level, Level) and level.level_id == level_or_id:
                return level

        state = self._players.get(player_id)
        level = state.get("level") if state else None
        if isinstance(level, Level):
            return level

        return None
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
        payload_meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
        payload_body = event.get("payload") if isinstance(event.get("payload"), dict) else {}

        target = (
            event.get("target")
            or event.get("target_id")
            or payload_body.get("target")
            or payload_body.get("entity_name")
            or payload_body.get("entity_type")
            or payload_body.get("block_type")
        )

        meta = payload_meta or payload_body

        if not isinstance(event_type, str) or not event_type:
            return None

        normalized = {
            "event_type": event_type.lower(),
            "target": target,
            "meta": meta,
        }

        if event.get("count") is not None:
            normalized["count"] = event.get("count")

        if payload_body.get("quest_event"):
            normalized["quest_event"] = payload_body.get("quest_event")

        return normalized

    def _aggregate_rule_responses(
        self,
        state: Dict[str, Any],
        responses: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not responses:
            return None

        world_patch: Dict[str, Any] = {}
        nodes: List[Dict[str, Any]] = []
        completed: List[str] = []
        milestones: List[str] = []
        seen_completed: Set[str] = set()
        seen_milestones: Set[str] = set()

        session_lookup: Dict[str, TaskSession] = {
            session.id: session for session in self._iter_sessions(state)
        }
        milestone_lookup: Dict[str, TaskMilestone] = {}
        for session in session_lookup.values():
            for milestone in session.milestones:
                milestone_lookup[milestone.id] = milestone

        for resp in responses:
            if not isinstance(resp, dict):
                continue

            if resp.get("task_completed"):
                task_id = resp.get("task_id")
                if task_id and task_id not in seen_completed:
                    seen_completed.add(task_id)
                    completed.append(task_id)

                    session = session_lookup.get(task_id)
                    if session:
                        state["last_completed_type"] = session.type

                    reward = resp.get("reward") or {}
                    world_patch = self._merge_patch(world_patch, reward.get("world_patch"))
                    if reward.get("npc_dialogue"):
                        world_patch = self._merge_patch(world_patch, {"npc_dialogue": reward["npc_dialogue"]})

                    dialogue = resp.get("dialogue") or {}
                    text = dialogue.get("on_complete")
                    if not text and session and session.dialogue:
                        text = session.dialogue.get("on_complete")

                    task_title = resp.get("task_title") or (
                        session.title if session and session.title else f"任务 {task_id}"
                    )
                    task_hint = resp.get("task_hint") or (
                        session.hint if session and session.hint else None
                    )
                    node_payload: Dict[str, Any] = {
                        "type": "task_complete",
                        "task_id": task_id,
                        "title": task_title,
                        "task_title": task_title,
                        "status": "complete",
                    }
                    if task_hint:
                        node_payload["hint"] = task_hint
                        node_payload["task_hint"] = task_hint
                    if text:
                        node_payload["text"] = text

                    progress_val = resp.get("task_progress")
                    if progress_val is None and session:
                        progress_val = session.progress
                    if progress_val is not None:
                        node_payload["progress"] = progress_val

                    count_val = resp.get("task_count")
                    if count_val is None and session:
                        count_val = session.count
                    if count_val is not None:
                        node_payload["count"] = count_val

                    nodes.append(node_payload)

            if resp.get("milestone_completed"):
                milestone_id = resp.get("milestone_id")
                if milestone_id and milestone_id not in seen_milestones:
                    seen_milestones.add(milestone_id)
                    milestones.append(milestone_id)

                    session = session_lookup.get(resp.get("task_id"))
                    milestone = milestone_lookup.get(milestone_id)

                    milestone_title = resp.get("milestone_title")
                    if not milestone_title:
                        if milestone and milestone.title:
                            milestone_title = milestone.title
                        elif session and session.title:
                            milestone_title = f"{session.title} · 阶段"
                        else:
                            milestone_title = f"阶段完成：{milestone_id}"

                    milestone_hint = resp.get("milestone_hint")
                    if not milestone_hint and milestone and milestone.hint:
                        milestone_hint = milestone.hint
                    if not milestone_hint and session and session.hint:
                        milestone_hint = session.hint

                    milestone_text = resp.get("milestone_text")
                    if not milestone_text and milestone and milestone.title and milestone_title != milestone.title:
                        milestone_text = milestone.title
                    if not milestone_text:
                        milestone_text = "继续保持，加油完成剩余目标！"

                    node_payload: Dict[str, Any] = {
                        "type": "task_milestone",
                        "task_id": resp.get("task_id"),
                        "milestone_id": milestone_id,
                        "title": milestone_title,
                        "text": milestone_text,
                        "status": "milestone",
                    }
                    if session and session.title:
                        node_payload["task_title"] = session.title
                    if milestone_hint:
                        node_payload["hint"] = milestone_hint
                        if session and not node_payload.get("task_hint"):
                            node_payload["task_hint"] = session.hint or milestone_hint
                    elif session and session.hint:
                        node_payload["hint"] = session.hint
                        node_payload.setdefault("task_hint", session.hint)

                    progress_val = resp.get("task_progress")
                    if progress_val is None and session:
                        progress_val = session.progress
                    if progress_val is not None:
                        node_payload["progress"] = progress_val

                    count_val = resp.get("task_count")
                    if count_val is None:
                        count_val = milestone.count if milestone else None
                    if count_val is not None:
                        node_payload["count"] = count_val

                    milestone_count = resp.get("milestone_count")
                    if milestone_count is not None:
                        node_payload["milestone_count"] = milestone_count
                    if milestone and milestone.count and "milestone_count" not in node_payload:
                        node_payload["milestone_count"] = milestone.count

                    nodes.append(node_payload)

            if resp.get("matched") and not resp.get("task_completed"):
                task_id = resp.get("task_id")
                if not task_id:
                    continue

                session = session_lookup.get(task_id)
                remaining_raw = resp.get("remaining")
                try:
                    remaining_val = max(0, int(remaining_raw))
                except (TypeError, ValueError):
                    remaining_val = 0
                if remaining_val <= 0:
                    continue

                task_title = resp.get("task_title") or (
                    session.title if session and session.title else f"任务：{task_id}"
                )
                task_hint = resp.get("task_hint") or (
                    session.hint if session and session.hint else None
                )

                node_payload = {
                    "type": "task_progress",
                    "task_id": task_id,
                    "title": task_title,
                    "task_title": task_title,
                    "status": "progress",
                    "remaining": remaining_val,
                    "text": f"剩余 {remaining_val} 项。",
                }

                if task_hint:
                    node_payload["hint"] = task_hint
                    node_payload["task_hint"] = task_hint

                progress_val = resp.get("task_progress")
                if progress_val is None and session:
                    progress_val = session.progress
                if progress_val is not None:
                    node_payload["progress"] = progress_val

                count_val = resp.get("task_count")
                if count_val is None and session:
                    count_val = session.count
                if count_val is not None:
                    node_payload["count"] = count_val

                nodes.append(node_payload)

        if not nodes and not world_patch and not completed and not milestones:
            return None

        summary: Dict[str, Any] = {"nodes": nodes}
        if world_patch:
            summary["world_patch"] = world_patch
        if completed:
            summary["completed_tasks"] = completed
        if milestones:
            summary["milestones"] = milestones
        return summary

    def _create_session(self, task: Dict[str, Any], index: int) -> TaskSession:
        if not isinstance(task, dict):
            if is_dataclass(task):
                task = {key: getattr(task, key) for key in getattr(task, "__dataclass_fields__", {})}
            else:
                task = dict(getattr(task, "__dict__", {}))
        if not isinstance(task, dict):
            task = {}
        def _clean_str(value: Any) -> Optional[str]:
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        task_id = str(task.get("id") or f"task_{index:02d}")
        task_type = str(task.get("type") or "custom").lower()
        target = task.get("target") or {}
        count = max(1, int(task.get("count") or 1))
        reward_raw = task.get("reward") or task.get("rewards")
        if isinstance(reward_raw, list):
            reward = next((item for item in reward_raw if isinstance(item, dict)), {})
        elif isinstance(reward_raw, dict):
            reward = reward_raw
        else:
            reward = {}

        dialogue_raw = task.get("dialogue") or task.get("dialogues")
        if isinstance(dialogue_raw, dict):
            dialogue = dialogue_raw
        elif isinstance(dialogue_raw, str):
            dialogue = {"text": dialogue_raw}
        else:
            dialogue = {}
        rule_refs = list(task.get("rule_refs", []) or [])

        task_title = _clean_str(task.get("title")) or _clean_str(task.get("name")) or _clean_str(task.get("label"))
        task_hint = (
            _clean_str(task.get("hint"))
            or _clean_str(task.get("summary"))
            or _clean_str(task.get("description"))
        )

        issue_node_raw = task.get("issue_node")
        issue_node = issue_node_raw if isinstance(issue_node_raw, dict) else None
        if issue_node:
            task_title = task_title or _clean_str(issue_node.get("title"))
            task_hint = task_hint or _clean_str(issue_node.get("hint")) or _clean_str(issue_node.get("text"))

        milestone_configs = task.get("milestones") or []
        milestones: List[TaskMilestone] = []
        for idx, raw in enumerate(milestone_configs):
            milestone_data: Optional[Dict[str, Any]] = None
            if isinstance(raw, dict):
                milestone_data = dict(raw)
            elif is_dataclass(raw):
                milestone_data = {key: getattr(raw, key) for key in getattr(raw, "__dataclass_fields__", {})}
            elif isinstance(raw, str):
                milestone_data = {"id": raw, "title": raw}
            else:
                attrs = getattr(raw, "__dict__", None)
                if isinstance(attrs, dict):
                    milestone_data = dict(attrs)
            if not milestone_data:
                continue

            milestone_id = _clean_str(milestone_data.get("id")) or _clean_str(milestone_data.get("name"))
            milestone_id = milestone_id or f"{task_id}_milestone_{idx:02d}"
            milestone_title = _clean_str(milestone_data.get("title")) or _clean_str(milestone_data.get("name"))
            milestone_hint = (
                _clean_str(milestone_data.get("hint"))
                or _clean_str(milestone_data.get("summary"))
                or _clean_str(milestone_data.get("description"))
            )
            milestone_target = (
                _clean_str(milestone_data.get("target"))
                or _clean_str(milestone_data.get("entity"))
                or _clean_str(milestone_data.get("location"))
            )
            try:
                milestone_count = max(1, int(milestone_data.get("count") or milestone_data.get("required") or 1))
            except (TypeError, ValueError):
                milestone_count = 1

            milestones.append(TaskMilestone(
                id=milestone_id,
                title=milestone_title,
                hint=milestone_hint,
                target=milestone_target,
                count=milestone_count,
            ))

        session = TaskSession(
            id=task_id,
            type=task_type,
            target=target,
            title=task_title or "",
            hint=task_hint,
            count=count,
            reward=reward,
            dialogue=dialogue,
            milestones=milestones,
            rule_refs=rule_refs,
        )

        if not session.title:
            if isinstance(target, dict):
                fallback = _clean_str(target.get("name") or target.get("type"))
            elif isinstance(target, str):
                fallback = _clean_str(target)
            else:
                fallback = None
            session.title = fallback or f"任务：{session.id}"

        if not session.hint:
            session.hint = self._default_issue_text(session)

        if issue_node:
            setattr(session, "issue_node", issue_node)

        return session

    def _merge_response_payload(
        self,
        base: Optional[Dict[str, Any]],
        addition: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not addition:
            return base

        merged: Dict[str, Any] = {}
        if base:
            merged.update(base)

        nodes = list(merged.get("nodes") or [])
        added_nodes = addition.get("nodes") if isinstance(addition.get("nodes"), list) else []
        if added_nodes:
            nodes.extend(added_nodes)
        if nodes:
            merged["nodes"] = nodes

        world_patch = self._merge_patch(merged.get("world_patch"), addition.get("world_patch"))
        if world_patch:
            merged["world_patch"] = world_patch
        elif "world_patch" in merged and not merged["world_patch"]:
            merged.pop("world_patch")

        for key in ("completed_tasks", "milestones"):
            existing = list(merged.get(key) or [])
            incoming = addition.get(key)
            if isinstance(incoming, list) and incoming:
                existing.extend(incoming)
            if existing:
                merged[key] = existing
            elif key in merged:
                merged.pop(key)

        for key, value in addition.items():
            if key in {"nodes", "world_patch", "completed_tasks", "milestones"}:
                continue
            if value is None:
                continue
            if isinstance(value, list):
                existing_list = merged.get(key)
                if isinstance(existing_list, list):
                    merged[key] = existing_list + value
                else:
                    merged[key] = list(value)
            else:
                merged[key] = value

        return merged or base

    def _issue_next_task(self, state: Dict[str, Any], level: Level, beat: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sessions = state.get("tasks", [])
        for session in sessions:
            if session.status == "pending":
                session.mark_issued(beat.get("id"))
                state["issued_index"] = sessions.index(session)
                return self._build_issue_node(level, session)
        return None

    def _collect_rewards(self, state: Dict[str, Any], level: Level) -> Optional[Dict[str, Any]]:
        world_patch: Dict[str, Any] = {}
        nodes: List[Dict[str, Any]] = []
        completed: List[str] = []
        for session in self._iter_sessions(state):
            if session.status == "completed" and not getattr(session, "rewarded", False):
                reward = session.reward or {}
                world_patch = self._merge_patch(world_patch, reward.get("world_patch"))
                if "npc_dialogue" in reward:
                    world_patch = self._merge_patch(world_patch, {"npc_dialogue": reward["npc_dialogue"]})
                nodes.append(self._build_reward_node(level, session))
                setattr(session, "rewarded", True)
                state["completed_count"] += 1
                state["last_completed_type"] = session.type
                completed.append(session.id)

        if not nodes and not world_patch:
            return None

        return {
            "world_patch": world_patch,
            "nodes": nodes,
            "completed_tasks": completed,
        }

    def _all_tasks_completed(self, state: Dict[str, Any]) -> bool:
        tasks = list(self._iter_sessions(state))
        return bool(tasks) and all(session.status == "completed" for session in tasks)

    def _build_issue_node(self, level: Level, session: TaskSession) -> Dict[str, Any]:
        node = getattr(session, "issue_node", {}) or {}
        title = node.get("title") or session.title or f"任务：{session.id}"
        hint = node.get("hint") or session.hint
        text = node.get("text") or hint or self._default_issue_text(session)
        payload = {
            "title": title,
            "text": text,
            "type": "task",
            "task_id": session.id,
            "status": "issued",
        }
        if hint:
            payload["hint"] = hint
        return payload

    def _build_reward_node(self, level: Level, session: TaskSession) -> Dict[str, Any]:
        text = session.dialogue.get("on_complete") or "任务完成，奖励已发放。"
        payload = {
            "title": session.title or f"任务：{session.id}",
            "text": text,
            "type": "task_complete",
            "task_id": session.id,
            "status": "complete",
        }
        if session.hint:
            payload["hint"] = session.hint
        return payload

    def _build_summary_node(self, level: Level, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": f"{level.title} · 任务总结",
            "text": "全部任务已完成，你可以随时返回昆明湖。",
            "hint": "输入 /advance 或使用出口回到中心。",
            "type": "task_summary",
            "status": "summary",
        }

    def _default_issue_text(self, session: TaskSession) -> str:
        task_type = session.type
        target = session.target
        count = session.count
        if isinstance(target, dict):
            name = target.get("name") or target.get("type") or target.get("id")
        else:
            name = str(target) if target not in ({}, None, "") else None
        name = name or "任务目标"
        return f"完成 {task_type} ×{count}（目标：{name}）"
    def _iter_sessions(self, state: Dict[str, Any]) -> Iterable[TaskSession]:
        return state.get("tasks", [])

    def _iter_active_sessions(self, state: Dict[str, Any]) -> Iterable[TaskSession]:
        return [session for session in self._iter_sessions(state) if session.status == "issued"]

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
