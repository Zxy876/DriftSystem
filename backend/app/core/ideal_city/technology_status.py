"""Hydrate CityPhone technology status snapshot from Forge-authored summaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TechnologyStage(BaseModel):
    label: Optional[str] = None
    level: Optional[int] = None
    progress: Optional[float] = None

    model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})


class TechnologyEnergyStatus(BaseModel):
    generation: float = 0.0
    consumption: float = 0.0
    capacity: float = 0.0
    storage: float = 0.0


class TechnologyRisk(BaseModel):
    risk_id: str
    level: Optional[str] = None
    summary: Optional[str] = None


class TechnologyEvent(BaseModel):
    event_id: str
    category: Optional[str] = None
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None
    impact: Optional[str] = None

    model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})


class TechnologyStatusSnapshot(BaseModel):
    stage: Optional[TechnologyStage] = None
    energy: Optional[TechnologyEnergyStatus] = None
    risk_alerts: List[TechnologyRisk] = Field(default_factory=list)
    recent_events: List[TechnologyEvent] = Field(default_factory=list)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})


class TechnologyStatusRepository:
    """Load the `technology-status.json` payload produced by Forge."""

    def __init__(self, protocol_root: Path) -> None:
        self._file = protocol_root / "technology-status.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)

    def load_snapshot(self) -> TechnologyStatusSnapshot:
        if not self._file.exists():
            return TechnologyStatusSnapshot()
        try:
            payload = json.loads(self._file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return TechnologyStatusSnapshot()
        stage_payload = payload.get("stage")
        energy_payload = payload.get("energy")
        risks_payload = (
            payload.get("risks")
            or payload.get("risk_alerts")
            or payload.get("alerts")
            or []
        )
        events_payload = (
            payload.get("recent_events")
            or payload.get("events")
            or payload.get("event_log")
            or []
        )
        updated_at = self._coerce_datetime(payload.get("updated_at") or payload.get("timestamp"))
        stage = self._build_stage(stage_payload)
        energy = self._build_energy(energy_payload)
        risks = list(self._build_risks(risks_payload))
        events = list(self._build_events(events_payload))
        if updated_at is None and events:
            event_times = [event.occurred_at for event in events if event.occurred_at is not None]
            if event_times:
                updated_at = max(event_times)
        return TechnologyStatusSnapshot(
            stage=stage,
            energy=energy,
            risk_alerts=risks,
            recent_events=events,
            updated_at=updated_at,
        )

    def _build_stage(self, payload: object) -> Optional[TechnologyStage]:
        if isinstance(payload, dict):
            level = self._maybe_int(payload.get("level") or payload.get("current"))
            progress = self._maybe_float(payload.get("progress") or payload.get("percent"))
            label = (
                payload.get("label")
                or payload.get("name")
                or payload.get("description")
                or payload.get("phase")
            )
            return TechnologyStage(
                label=str(label) if label else None,
                level=level,
                progress=progress,
            )
        if isinstance(payload, str):
            return TechnologyStage(label=payload)
        if isinstance(payload, (int, float)):
            return TechnologyStage(level=int(payload))
        return None

    def _build_energy(self, payload: object) -> Optional[TechnologyEnergyStatus]:
        if not isinstance(payload, dict):
            return None
        generation = self._maybe_float(payload.get("generation")) or 0.0
        consumption = self._maybe_float(payload.get("consumption")) or 0.0
        capacity = self._maybe_float(payload.get("capacity")) or 0.0
        storage = self._maybe_float(
            payload.get("storage")
            or payload.get("buffer")
            or payload.get("reserve")
        ) or 0.0
        return TechnologyEnergyStatus(
            generation=generation,
            consumption=consumption,
            capacity=capacity,
            storage=storage,
        )

    def _build_risks(self, payload: object) -> Iterable[TechnologyRisk]:
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []
        risks: List[TechnologyRisk] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            risk_id = str(item.get("risk_id") or item.get("id") or item.get("code") or "").strip()
            if not risk_id:
                continue
            level_raw = item.get("level") or item.get("severity")
            level = str(level_raw).strip() if isinstance(level_raw, str) and level_raw.strip() else None
            summary_raw = item.get("summary") or item.get("description") or item.get("note")
            summary = str(summary_raw).strip() if isinstance(summary_raw, str) and summary_raw.strip() else None
            risks.append(
                TechnologyRisk(
                    risk_id=risk_id,
                    level=level,
                    summary=summary,
                )
            )
        return risks

    def _build_events(self, payload: object) -> Iterable[TechnologyEvent]:
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []
        events: List[TechnologyEvent] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            occurred_at = self._coerce_datetime(item.get("occurred_at") or item.get("timestamp"))
            event_id_raw = (
                item.get("event_id")
                or item.get("id")
                or item.get("type")
                or item.get("event_type")
            )
            if not event_id_raw:
                prefix_raw = item.get("event_type") or item.get("type") or "event"
                prefix = str(prefix_raw).strip() or "event"
                stage_hint = self._maybe_int(item.get("stage"))
                if occurred_at is not None:
                    suffix = str(int(occurred_at.timestamp()))
                    if stage_hint is not None:
                        event_id_raw = f"{prefix}-{stage_hint}-{suffix}"
                    else:
                        event_id_raw = f"{prefix}-{suffix}"
            event_id = str(event_id_raw).strip() if event_id_raw is not None else ""
            if not event_id:
                continue
            category_raw = item.get("category") or item.get("type") or item.get("event_type")
            category = str(category_raw).strip() if isinstance(category_raw, str) and category_raw.strip() else None
            description_raw = (
                item.get("description")
                or item.get("summary")
                or item.get("note")
                or item.get("message")
            )
            description = (
                str(description_raw).strip()
                if isinstance(description_raw, str) and description_raw.strip()
                else None
            )
            if (
                occurred_at is not None
                and category is not None
                and event_id == category
            ):
                suffix = str(int(occurred_at.timestamp()))
                stage_hint = self._maybe_int(item.get("stage"))
                if stage_hint is not None:
                    event_id = f"{event_id}-{stage_hint}-{suffix}"
                else:
                    event_id = f"{event_id}-{suffix}"
            impact_raw = item.get("impact") or item.get("effect") or item.get("status")
            impact = str(impact_raw).strip() if isinstance(impact_raw, str) and impact_raw.strip() else None
            events.append(
                TechnologyEvent(
                    event_id=event_id,
                    category=category,
                    description=description,
                    occurred_at=occurred_at,
                    impact=impact,
                )
            )
        return events

    def _coerce_datetime(self, value: object) -> Optional[datetime]:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        return None

    def _maybe_int(self, value: object) -> Optional[int]:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.strip():
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def _maybe_float(self, value: object) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            try:
                return float(value)
            except ValueError:
                return None
        return None