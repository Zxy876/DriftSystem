"""Structured world build-event recorder for video-ready timeline production.

Records block-level construction events emitted by Drift's build pipeline.
Events are written as JSONL to data/world_events/build_timeline.jsonl and
can be replayed or exported for OBS overlays and video post-production.

Each record includes:
- scene_id        string    logical scene or memory being reproduced
- plan_id         string    originating CreationPlan patch_id
- step_id         string    individual template step
- event_type      string    "block_place" | "block_fill" | "function_call" | etc.
- command         string    the raw MC command dispatched
- timestamp       str       ISO 8601 UTC
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


_SETBLOCK_RE = re.compile(
    r"^setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(\S+)", re.IGNORECASE
)
_FILL_RE = re.compile(
    r"^fill\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(\S+)",
    re.IGNORECASE,
)


@dataclass
class WorldBuildEvent:
    """A single structured world-build event."""

    event_type: str
    command: str
    timestamp: str
    plan_id: str
    step_id: str
    scene_id: str
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "scene_id": self.scene_id,
                "plan_id": self.plan_id,
                "step_id": self.step_id,
                "event_type": self.event_type,
                "command": self.command,
                "timestamp": self.timestamp,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
        )


class WorldBuildEventLog:
    """Append-only JSONL timeline of world-build events for a recording session."""

    def __init__(self, root: Optional[Path] = None) -> None:
        base = root or Path(__file__).resolve().parents[3] / "data" / "world_events"
        base.mkdir(parents=True, exist_ok=True)
        self._path = base / "build_timeline.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    def record_commands(
        self,
        commands: Iterable[str],
        *,
        plan_id: str,
        step_id: str,
        scene_id: str = "default",
    ) -> List[WorldBuildEvent]:
        """Parse and record a batch of MC commands as structured build events.

        Returns the list of events written so callers can inspect or assert.
        """
        events: List[WorldBuildEvent] = []
        timestamp = datetime.now(timezone.utc).isoformat()
        for command in commands:
            cmd = command.strip()
            if not cmd:
                continue
            event_type = _classify_command(cmd)
            meta = _extract_metadata(cmd)
            event = WorldBuildEvent(
                event_type=event_type,
                command=cmd,
                timestamp=timestamp,
                plan_id=plan_id,
                step_id=step_id,
                scene_id=scene_id,
                metadata=meta,
            )
            events.append(event)
        with self._path.open("a", encoding="utf-8") as fh:
            for event in events:
                fh.write(event.to_json())
                fh.write("\n")
        return events

    def load(self) -> List[WorldBuildEvent]:
        """Read all recorded events from the timeline file."""
        events: List[WorldBuildEvent] = []
        if not self._path.exists():
            return events
        for line in self._path.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(
                WorldBuildEvent(
                    scene_id=str(payload.get("scene_id", "")),
                    plan_id=str(payload.get("plan_id", "")),
                    step_id=str(payload.get("step_id", "")),
                    event_type=str(payload.get("event_type", "unknown")),
                    command=str(payload.get("command", "")),
                    timestamp=str(payload.get("timestamp", "")),
                    metadata=dict(payload.get("metadata", {})),
                )
            )
        return events


def _classify_command(command: str) -> str:
    lower = command.lower().lstrip()
    if lower.startswith("setblock "):
        return "block_place"
    if lower.startswith("fill "):
        return "block_fill"
    if lower.startswith("function "):
        return "function_call"
    if lower.startswith("summon "):
        return "entity_spawn"
    if lower.startswith("execute "):
        if " setblock " in lower:
            return "block_place"
        if " fill " in lower:
            return "block_fill"
        if " place " in lower:
            return "structure_place"
        if " function " in lower:
            return "function_call"
    return "command"


def _extract_metadata(command: str) -> Dict[str, object]:
    m = _SETBLOCK_RE.match(command)
    if m:
        return {
            "x": int(m.group(1)),
            "y": int(m.group(2)),
            "z": int(m.group(3)),
            "block": m.group(4),
        }
    m = _FILL_RE.match(command)
    if m:
        return {
            "x1": int(m.group(1)),
            "y1": int(m.group(2)),
            "z1": int(m.group(3)),
            "x2": int(m.group(4)),
            "y2": int(m.group(5)),
            "z2": int(m.group(6)),
            "block": m.group(7),
        }
    return {}
