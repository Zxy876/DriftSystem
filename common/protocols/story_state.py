"""Shared protocol objects for StoryStatePatch payloads.

This module defines a minimal contract that Minecraft scripts, backend agents,
and offline tooling can share when serialising ``StoryStatePatch`` payloads.  It
focuses on typing and light normalisation so that callers can coerce loosely
structured dictionaries (e.g. parsed from YAML, AI responses, or command output)
into a predictable schema before handing them to the backend ``StoryState``
manager.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, TypedDict
from typing import Literal


StoryMilestoneStatus = Literal["pending", "complete", "skipped"]


class StoryMilestoneUpdatePayload(TypedDict, total=False):
    """Contract for a single milestone patch entry."""

    status: StoryMilestoneStatus
    source: str
    note: str


class StoryStatePatchPayload(TypedDict, total=False):
    """Contract for StoryState patch payloads emitted by agents or scripts."""

    goals: List[str]
    logic_outline: List[str]
    resources: List[str]
    community_requirements: List[str]
    success_criteria: List[str]
    world_constraints: List[str]
    risk_register: List[str]
    risk_notes: List[str]
    notes: List[str]
    follow_up_questions: List[str]
    blocking: List[str]
    coverage: Dict[str, bool]
    motivation_score: int
    logic_score: int
    build_capability: int
    location_hint: str
    player_pose: Dict[str, Any]
    milestones: Dict[str, StoryMilestoneUpdatePayload]
    source_task: str
    npc_id: str
    timestamp: str


_LIST_FIELDS = {
    "goals",
    "logic_outline",
    "resources",
    "community_requirements",
    "success_criteria",
    "world_constraints",
    "risk_register",
    "risk_notes",
    "notes",
    "follow_up_questions",
    "blocking",
}

_INT_FIELDS = {"motivation_score", "logic_score", "build_capability"}
_STRING_FIELDS = {"location_hint", "source_task", "npc_id", "timestamp"}


def _coerce_list(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for raw in values:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _coerce_milestones(payload: Mapping[str, Any]) -> Dict[str, StoryMilestoneUpdatePayload]:
    result: Dict[str, StoryMilestoneUpdatePayload] = {}
    for key, value in payload.items():
        if not key:
            continue
        milestone_id = str(key).strip()
        if not milestone_id:
            continue
        if not isinstance(value, Mapping):
            continue
        entry: StoryMilestoneUpdatePayload = {}
        status = value.get("status")
        if isinstance(status, str):
            status_norm = status.strip().lower()
            if status_norm in {"pending", "complete", "skipped"}:
                entry["status"] = status_norm  # type: ignore[assignment]
        source = value.get("source")
        if isinstance(source, str) and source.strip():
            entry["source"] = source.strip()
        note = value.get("note")
        if isinstance(note, str) and note.strip():
            entry["note"] = note.strip()
        if entry:
            result[milestone_id] = entry
    return result


def coerce_story_state_patch(raw: Mapping[str, Any]) -> StoryStatePatchPayload:
    """Coerce a loosely structured mapping into a ``StoryStatePatchPayload``.

    The function filters out empty strings, removes duplicate list entries, and
    drops invalid milestone updates.  It never mutates the input mapping.
    """

    result: MutableMapping[str, Any] = {}

    for field in _LIST_FIELDS:
        values = raw.get(field)
        if isinstance(values, Iterable) and not isinstance(values, (str, bytes)):
            coerced = _coerce_list(values)
            if coerced:
                result[field] = coerced

    coverage = raw.get("coverage")
    if isinstance(coverage, Mapping):
        coverage_map: Dict[str, bool] = {}
        for key, value in coverage.items():
            label = str(key)
            coverage_map[label] = bool(value)
        if coverage_map:
            result["coverage"] = coverage_map

    for field in _INT_FIELDS:
        value = raw.get(field)
        if isinstance(value, (int, float)):
            result[field] = int(value)
        elif isinstance(value, str):
            text = value.strip()
            if text:
                try:
                    result[field] = int(float(text))
                except ValueError:
                    continue

    for field in _STRING_FIELDS:
        value = raw.get(field)
        if isinstance(value, str):
            text = value.strip()
            if text:
                result[field] = text

    pose = raw.get("player_pose")
    if isinstance(pose, Mapping) and pose:
        result["player_pose"] = {str(key): value for key, value in pose.items()}

    milestones = raw.get("milestones")
    if isinstance(milestones, Mapping) and milestones:
        coerced_milestones = _coerce_milestones(milestones)
        if coerced_milestones:
            result["milestones"] = coerced_milestones

    return result  # type: ignore[return-value]


__all__ = [
    "StoryMilestoneStatus",
    "StoryMilestoneUpdatePayload",
    "StoryStatePatchPayload",
    "coerce_story_state_patch",
]
