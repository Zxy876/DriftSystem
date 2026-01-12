"""Forge-facing helpers to publish technology status snapshots.

The writer keeps the on-disk `technology-status.json` file in sync with
the structures consumed by :class:`TechnologyStatusRepository`.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat(value: datetime) -> str:
    return _ensure_utc(value).isoformat()


def _load_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _atomic_write(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


@dataclass
class EnergySnapshot:
    generation: Optional[float] = None
    consumption: Optional[float] = None
    capacity: Optional[float] = None
    storage: Optional[float] = None

    def to_dict(self) -> Dict[str, float]:
        result: Dict[str, float] = {}
        if self.generation is not None:
            result["generation"] = float(self.generation)
        if self.consumption is not None:
            result["consumption"] = float(self.consumption)
        if self.capacity is not None:
            result["capacity"] = float(self.capacity)
        if self.storage is not None:
            result["storage"] = float(self.storage)
        return result


@dataclass
class RiskEvent:
    risk_id: str
    level: Optional[str] = None
    summary: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        payload: Dict[str, str] = {"risk_id": self.risk_id}
        if self.level:
            payload["level"] = self.level
        if self.summary:
            payload["summary"] = self.summary
        return payload


@dataclass
class TechnologyEvent:
    event_id: str
    category: Optional[str] = None
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None
    impact: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {"event_id": self.event_id}
        if self.category:
            payload["category"] = self.category
        if self.description:
            payload["description"] = self.description
        if self.impact:
            payload["impact"] = self.impact
        if self.occurred_at is not None:
            payload["occurred_at"] = _isoformat(self.occurred_at)
        return payload


@dataclass
class StageSnapshot:
    level: Optional[int] = None
    label: Optional[str] = None
    progress: Optional[float] = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {}
        if self.level is not None:
            payload["level"] = int(self.level)
        if self.label:
            payload["label"] = self.label
        if self.progress is not None:
            payload["progress"] = float(self.progress)
        return payload


class TechnologyStatusWriter:
    """Pragmatic writer utility for `technology-status.json`.

    Forge runtime can call the fluent methods to update different parts of the
    snapshot. Every update persists atomically by default to avoid presenting
    partial content to the plugin.
    """

    def __init__(self, protocol_root: Path, *, auto_timestamp: bool = True) -> None:
        self._file = Path(protocol_root) / "technology-status.json"
        self._lock = threading.Lock()
        self._state: Dict[str, object] = _load_json(self._file)
        self._auto_timestamp = auto_timestamp

    def update_stage(
        self,
        stage: StageSnapshot,
        *,
        updated_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> None:
        with self._lock:
            self._state["stage"] = stage.to_dict()
            self._touch(updated_at)
            if commit:
                self._write()

    def update_energy(
        self,
        energy: EnergySnapshot,
        *,
        updated_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> None:
        with self._lock:
            energy_payload = energy.to_dict()
            if energy_payload:
                self._state["energy"] = energy_payload
            else:
                self._state.pop("energy", None)
            self._touch(updated_at)
            if commit:
                self._write()

    def record_risk(
        self,
        risk: RiskEvent,
        *,
        replace: bool = True,
        updated_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> None:
        with self._lock:
            risks: List[Dict[str, object]] = list(self._state.get("risks") or [])
            if replace:
                risks = [item for item in risks if item.get("risk_id") != risk.risk_id]
            risks.append(risk.to_dict())
            self._state["risks"] = risks
            self._touch(updated_at)
            if commit:
                self._write()

    def record_event(
        self,
        event: TechnologyEvent,
        *,
        replace: bool = True,
        updated_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> None:
        with self._lock:
            events: List[Dict[str, object]] = list(
                self._state.get("recent_events")
                or self._state.get("events")
                or self._state.get("event_log")
                or []
            )
            if replace:
                events = [item for item in events if item.get("event_id") != event.event_id]
            events.append(event.to_dict())
            self._state["recent_events"] = events
            # ensure compatibility if other keys existed previously
            self._state.pop("events", None)
            self._state.pop("event_log", None)
            if event.occurred_at is not None and updated_at is None:
                updated_at = event.occurred_at
            self._touch(updated_at)
            if commit:
                self._write()

    def remove_risk(self, risk_id: str, *, commit: bool = True) -> None:
        with self._lock:
            risks = [
                item
                for item in list(self._state.get("risks") or [])
                if item.get("risk_id") != risk_id
            ]
            if risks:
                self._state["risks"] = risks
            else:
                self._state.pop("risks", None)
            if commit:
                self._write()

    def remove_event(self, event_id: str, *, commit: bool = True) -> None:
        with self._lock:
            events = [
                item
                for item in list(self._state.get("recent_events") or [])
                if item.get("event_id") != event_id
            ]
            if events:
                self._state["recent_events"] = events
            else:
                self._state.pop("recent_events", None)
            if commit:
                self._write()

    def set_vitals(
        self,
        *,
        active_systems: Optional[int] = None,
        offline_systems: Optional[int] = None,
        updated_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> None:
        with self._lock:
            vitals = {
                "active_systems": active_systems,
                "offline_systems": offline_systems,
            }
            filtered = {key: value for key, value in vitals.items() if value is not None}
            if filtered:
                self._state["vitals"] = {key: int(value) for key, value in filtered.items()}
            else:
                self._state.pop("vitals", None)
            self._touch(updated_at)
            if commit:
                self._write()

    def clear_events(self, *, commit: bool = True) -> None:
        with self._lock:
            self._state.pop("recent_events", None)
            self._state.pop("events", None)
            self._state.pop("event_log", None)
            if commit:
                self._write()

    def set_updated_at(self, value: datetime, *, commit: bool = True) -> None:
        with self._lock:
            self._state["updated_at"] = _isoformat(value)
            if commit:
                self._write()

    def commit(self) -> None:
        with self._lock:
            self._write()

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            return json.loads(json.dumps(self._state))

    def _touch(self, updated_at: Optional[datetime]) -> None:
        if updated_at is not None:
            self._state["updated_at"] = _isoformat(updated_at)
        elif self._auto_timestamp:
            self._state["updated_at"] = _isoformat(datetime.now(timezone.utc))

    def _write(self) -> None:
        _atomic_write(self._file, self._state)
