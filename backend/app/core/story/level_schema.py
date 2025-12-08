"""Phase 1.5 level schema scaffolding.

This module is intentionally lightweight and backward compatible. It exposes
dataclasses that model the planned extensions without forcing the existing
`story_loader` implementation to change immediately. Callers can opt-in by
attaching these structures to legacy level instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Scene configuration
# ---------------------------------------------------------------------------


@dataclass
class SceneTeleport:
    """Absolute teleport target for a scene."""

    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    yaw: Optional[float] = None
    pitch: Optional[float] = None

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "SceneTeleport":
        if not isinstance(data, dict):
            return SceneTeleport()
        return SceneTeleport(
            x=_coerce_float(data.get("x")),
            y=_coerce_float(data.get("y")),
            z=_coerce_float(data.get("z")),
            yaw=_coerce_float(data.get("yaw")),
            pitch=_coerce_float(data.get("pitch")),
        )


@dataclass
class SceneEnvironment:
    """Minimal environment descriptor for deterministic scenes."""

    weather: Optional[str] = None
    time: Optional[str] = None
    lighting: Optional[str] = None

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "SceneEnvironment":
        if not isinstance(data, dict):
            return SceneEnvironment()
        return SceneEnvironment(
            weather=_coerce_str(data.get("weather")),
            time=_coerce_str(data.get("time")),
            lighting=_coerce_str(data.get("lighting")),
        )


@dataclass
class SceneConfig:
    """Aggregate scene definition for Phase 1.5."""

    world: Optional[str] = None
    teleport: Optional[SceneTeleport] = None
    environment: Optional[SceneEnvironment] = None
    structures: List[str] = field(default_factory=list)
    npc_skins: List[Dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "SceneConfig":
        if not isinstance(data, dict):
            return SceneConfig()

        teleport = SceneTeleport.from_dict(data.get("teleport"))
        environment = SceneEnvironment.from_dict(data.get("environment"))

        return SceneConfig(
            world=_coerce_str(data.get("world")),
            teleport=teleport,
            environment=environment,
            structures=_coerce_str_list(data.get("structures")),
            npc_skins=_coerce_dict_list(data.get("npc_skins")),
        )


# ---------------------------------------------------------------------------
# Narrative beats and rules
# ---------------------------------------------------------------------------


@dataclass
class BeatConfig:
    """Narrative beat metadata."""

    id: str = ""
    trigger: Optional[str] = None
    scene_patch: Optional[str] = None
    rule_refs: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "BeatConfig":
        if not isinstance(data, dict):
            return BeatConfig()
        return BeatConfig(
            id=_coerce_str(data.get("id")) or "",
            trigger=_coerce_str(data.get("trigger")),
            scene_patch=_coerce_str(data.get("scene_patch")),
            rule_refs=_coerce_str_list(data.get("rule_refs")),
        )


@dataclass
class RuleListener:
    """Listener descriptor for rule graph events."""

    type: Optional[str] = None
    targets: List[str] = field(default_factory=list)
    quest_event: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "RuleListener":
        if not isinstance(data, dict):
            return RuleListener()
        listener = RuleListener(
            type=_coerce_str(data.get("type")),
            targets=_coerce_str_list(data.get("targets")),
            quest_event=_coerce_str(data.get("quest_event")),
            metadata=dict(data.get("metadata") or {}),
        )
        return listener


@dataclass
class RuleGraphConfig:
    """Wrapper for rule listeners."""

    listeners: List[RuleListener] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "RuleGraphConfig":
        if not isinstance(data, dict):
            return RuleGraphConfig()
        raw_listeners = data.get("listeners") or []
        listeners = [RuleListener.from_dict(item) for item in _coerce_list(raw_listeners)]
        return RuleGraphConfig(listeners=listeners)


# ---------------------------------------------------------------------------
# Tasks and rewards
# ---------------------------------------------------------------------------


@dataclass
class TaskCondition:
    """Basic task requirement placeholder."""

    item: Optional[str] = None
    entity: Optional[str] = None
    location: Optional[str] = None
    count: Optional[int] = None

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "TaskCondition":
        if not isinstance(data, dict):
            return TaskCondition()
        return TaskCondition(
            item=_coerce_str(data.get("item")),
            entity=_coerce_str(data.get("entity")),
            location=_coerce_str(data.get("location")),
            count=_coerce_int(data.get("count")),
        )


@dataclass
class TaskReward:
    """High-level task reward descriptor."""

    type: Optional[str] = None
    amount: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "TaskReward":
        if not isinstance(data, dict):
            return TaskReward()
        return TaskReward(
            type=_coerce_str(data.get("type")),
            amount=_coerce_int(data.get("amount")),
            data=dict(data.get("data") or {}),
        )


@dataclass
class TaskConfig:
    """Minimal quest/task metadata."""

    id: str = ""
    type: Optional[str] = None
    conditions: List[TaskCondition] = field(default_factory=list)
    milestones: List[str] = field(default_factory=list)
    rewards: List[TaskReward] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "TaskConfig":
        if not isinstance(data, dict):
            return TaskConfig()
        conditions = [
            TaskCondition.from_dict(item) for item in _coerce_list(data.get("conditions"))
        ]
        rewards = [TaskReward.from_dict(item) for item in _coerce_list(data.get("rewards"))]
        return TaskConfig(
            id=_coerce_str(data.get("id")) or "",
            type=_coerce_str(data.get("type")),
            conditions=conditions,
            milestones=_coerce_str_list(data.get("milestones")),
            rewards=rewards,
        )


@dataclass
class ExitConfig:
    """Exit speech configuration."""

    phrase_aliases: List[str] = field(default_factory=list)
    return_spawn: Optional[str] = None
    teleport: Optional[SceneTeleport] = None

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "ExitConfig":
        if not isinstance(data, dict):
            return ExitConfig()
        return ExitConfig(
            phrase_aliases=_coerce_str_list(data.get("phrase_aliases")),
            return_spawn=_coerce_str(data.get("return_spawn")),
            teleport=SceneTeleport.from_dict(data.get("teleport")),
        )


@dataclass
class LevelExtensions:
    """Phase 1.5 extension fields to be attached to legacy level objects."""

    beats: List[BeatConfig] = field(default_factory=list)
    scene: Optional[SceneConfig] = None
    rules: Optional[RuleGraphConfig] = None
    tasks: List[TaskConfig] = field(default_factory=list)
    exit: Optional[ExitConfig] = None

    @staticmethod
    def from_payload(payload: Optional[Dict[str, Any]]) -> "LevelExtensions":
        """Parse extension payload into structured dataclasses.

        `payload` should mirror the additional Phase 1.5 keys. Missing entries are
        ignored so that callers can opt-in gradually.
        """

        payload = payload or {}
        narrative = payload.get("narrative") or {}
        raw_beats = narrative.get("beats") or payload.get("beats") or []
        scene = SceneConfig.from_dict(payload.get("scene"))
        rules = RuleGraphConfig.from_dict(payload.get("rules"))
        tasks = [TaskConfig.from_dict(item) for item in _coerce_list(payload.get("tasks"))]
        exit_cfg = ExitConfig.from_dict(payload.get("exit"))

        beats = [BeatConfig.from_dict(item) for item in _coerce_list(raw_beats)]

        return LevelExtensions(
            beats=beats,
            scene=scene,
            rules=rules,
            tasks=tasks,
            exit=exit_cfg,
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def ensure_level_extensions(level: Any, payload: Optional[Dict[str, Any]] = None) -> LevelExtensions:
    """Attach Phase 1.5 fields to a legacy level object if missing.

    This helper is safe to call repeatedly. It uses ``setattr`` so the legacy
    ``Level`` dataclass from ``story_loader`` gains the new attributes without
    altering its constructor.
    """

    existing = LevelExtensions.from_payload(payload)

    for attr, value in (
        ("beats", existing.beats),
        ("scene", existing.scene),
        ("rules", existing.rules),
        ("tasks", existing.tasks),
        ("exit", existing.exit),
    ):
        if not hasattr(level, attr):
            setattr(level, attr, value)
    return existing


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _coerce_str_list(value: Any) -> List[str]:
    return [item for item in (_coerce_str(v) for v in _coerce_list(value)) if item]


def _coerce_dict_list(value: Any) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for item in _coerce_list(value):
        if isinstance(item, dict):
            results.append(dict(item))
    return results


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
