"""CityPhone social feedback ingestion from Forge-provided artefacts."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SocialFeedbackCategory = Literal["praise", "concern", "controversy", "regulation_proposal"]


class SocialFeedbackEntry(BaseModel):
    entry_id: str
    category: SocialFeedbackCategory
    title: str
    body: str
    issued_at: datetime
    stage: Optional[int] = None
    trust_delta: float = 0.0
    stress_delta: float = 0.0
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})


class SocialFeedbackSnapshot(BaseModel):
    entries: List[SocialFeedbackEntry] = Field(default_factory=list)
    trust_index: float = 0.0
    stress_index: float = 0.0
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})


class SocialAtmosphereEffect(BaseModel):
    """Recommended in-game ambience derived from social feedback."""

    mood: str
    intensity: str
    particle: str
    particle_count: int
    particle_radius: float
    sound: Optional[str] = None
    weather: str = "clear"
    headline: str = "城市舆论稳定"
    detail_lines: List[str] = Field(default_factory=list)
    dominant_category: Optional[SocialFeedbackCategory] = None


class SocialAtmospherePayload(BaseModel):
    snapshot: SocialFeedbackSnapshot
    effect: SocialAtmosphereEffect


class SocialFeedbackRepository:
    """Read Forge-authored social feedback feeds for CityPhone presentation."""

    def __init__(self, protocol_root: Path) -> None:
        self._root = protocol_root / "cityphone" / "social-feed"
        self._root.mkdir(parents=True, exist_ok=True)
        self._events_file = self._root / "events.jsonl"
        self._metrics_file = self._root / "metrics.json"

    def load_snapshot(self, *, limit: int = 20) -> SocialFeedbackSnapshot:
        entries = list(self._load_entries(limit))
        metrics = self._load_metrics()
        updated_at = metrics.get("updated_at")
        if updated_at is None and entries:
            updated_at = max(entry.issued_at for entry in entries)
        return SocialFeedbackSnapshot(
            entries=entries,
            trust_index=float(metrics.get("trust_index", 0.0)),
            stress_index=float(metrics.get("stress_index", 0.0)),
            updated_at=updated_at,
        )

    def load_atmosphere(self, *, limit: int = 5) -> SocialAtmospherePayload:
        snapshot = self.load_snapshot(limit=max(limit, 0) or 20)
        trimmed_entries = snapshot.entries[:limit] if limit else snapshot.entries
        trimmed_snapshot = SocialFeedbackSnapshot(
            entries=trimmed_entries,
            trust_index=snapshot.trust_index,
            stress_index=snapshot.stress_index,
            updated_at=snapshot.updated_at,
        )
        effect = derive_social_atmosphere(snapshot, highlight_count=len(trimmed_entries))
        return SocialAtmospherePayload(snapshot=trimmed_snapshot, effect=effect)

    def _load_entries(self, limit: int) -> Iterable[SocialFeedbackEntry]:
        if not self._events_file.exists():
            return []
        entries: List[SocialFeedbackEntry] = []
        with self._events_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                if limit and len(entries) >= limit:
                    break
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                entry = self._build_entry(payload)
                if entry is None:
                    continue
                entries.append(entry)
        entries.sort(key=lambda item: item.issued_at, reverse=True)
        return entries

    def _build_entry(self, payload: dict) -> Optional[SocialFeedbackEntry]:
        issued_at = self._coerce_datetime(payload.get("issued_at") or payload.get("timestamp"))
        if issued_at is None:
            return None
        try:
            entry_id = self._clean_text(payload.get("entry_id") or payload.get("id"))
            category = self._resolve_category(payload.get("category"))
            title = self._clean_text(payload.get("title") or payload.get("summary"))
            body = self._clean_text(payload.get("body") or payload.get("summary"))
            stage_value = self._maybe_int(payload.get("stage"))
            trust_delta = float(payload.get("trust_delta", 0.0) or 0.0)
            stress_delta = float(payload.get("stress_delta", 0.0) or 0.0)
            tags = self._collect_tags(payload.get("tags"))
            if entry_id and category and title:
                return SocialFeedbackEntry(
                    entry_id=entry_id,
                    category=category,
                    title=title,
                    body=body or title,
                    issued_at=issued_at,
                    stage=stage_value,
                    trust_delta=trust_delta,
                    stress_delta=stress_delta,
                    tags=tags,
                )
        except Exception:
            return None
        return self._build_stage_advance_entry(payload, issued_at)

    def _load_metrics(self) -> dict:
        if not self._metrics_file.exists():
            return {}
        try:
            payload = json.loads(self._metrics_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        metrics: dict = {}
        trust_value = payload.get("trust_index")
        if trust_value is None and "value" in payload:
            trust_value = payload.get("value")
        if trust_value is not None:
            metrics["trust_index"] = float(trust_value or 0.0)
        if "stress_index" in payload:
            metrics["stress_index"] = float(payload.get("stress_index", 0.0) or 0.0)
        updated_raw = payload.get("updated_at") or payload.get("timestamp")
        dt_value = self._coerce_datetime(updated_raw)
        if dt_value is not None:
            metrics["updated_at"] = dt_value
        return metrics

    def _coerce_datetime(self, value: object) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        return None

    def _resolve_category(self, value: object) -> Optional[SocialFeedbackCategory]:
        if not isinstance(value, str):
            return None
        lowered = value.lower()
        mapping = {
            "praise": "praise",
            "concern": "concern",
            "controversy": "controversy",
            "regulation_proposal": "regulation_proposal",
            "regulation-proposal": "regulation_proposal",
        }
        return mapping.get(lowered)

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

    def _collect_tags(self, value: object) -> List[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, Iterable):
            result: List[str] = []
            for item in value:
                text = str(item).strip()
                if text:
                    result.append(text)
            return result
        return []

    def _clean_text(self, value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        return ""

    def _build_stage_advance_entry(
        self,
        payload: dict,
        issued_at: datetime,
    ) -> Optional[SocialFeedbackEntry]:
        event_type = self._clean_text(payload.get("event_type") or payload.get("type"))
        if event_type != "stage_advance":
            return None
        stage_value = self._maybe_int(payload.get("stage"))
        scenario_id = self._clean_text(payload.get("scenario_id"))
        scenario_version = self._clean_text(payload.get("scenario_version"))
        summary = self._clean_text(payload.get("summary"))
        player_name = self._clean_text(payload.get("player_name")) or self._clean_text(payload.get("player_id"))
        entry_id = self._clean_text(payload.get("entry_id") or payload.get("id"))
        if not entry_id:
            suffix = str(int(issued_at.timestamp()))
            if stage_value is not None:
                entry_id = f"{event_type}-{stage_value}-{suffix}"
            else:
                entry_id = f"{event_type}-{suffix}"
        title = f"阶段 {stage_value} 推进完成" if stage_value is not None else "阶段推进完成"
        details: List[str] = []
        if player_name:
            details.append(f"触发者 {player_name}")
        if scenario_id:
            label = scenario_id if not scenario_version else f"{scenario_id} {scenario_version}".strip()
            details.append(f"场景 {label}")
        if summary:
            details.append(summary)
        body = "，".join(details) if details else "阶段推进已完成。"
        tags_source = payload.get("tags")
        if not tags_source:
            extras = [event_type]
            if scenario_id:
                extras.append(scenario_id)
            tags_source = extras
        try:
            return SocialFeedbackEntry(
                entry_id=entry_id,
                category="praise",
                title=title,
                body=body,
                issued_at=issued_at,
                stage=stage_value,
                trust_delta=float(payload.get("trust_delta") or 0.0),
                stress_delta=float(payload.get("stress_delta") or 0.0),
                tags=self._collect_tags(tags_source),
            )
        except Exception:
            return None


def derive_social_atmosphere(
    snapshot: SocialFeedbackSnapshot,
    *,
    highlight_count: int = 3,
) -> SocialAtmosphereEffect:
    """Map social metrics to an ambient effect profile for Minecraft presentation."""

    entries = snapshot.entries
    category_counter: Counter[SocialFeedbackCategory] = Counter(entry.category for entry in entries)
    dominant_category: Optional[SocialFeedbackCategory] = None
    if category_counter:
        dominant_category = category_counter.most_common(1)[0][0]

    trust = float(snapshot.trust_index or 0.0)
    stress = float(snapshot.stress_index or 0.0)
    score = trust - stress

    mood = "balanced"
    intensity = "low"
    particle = "NOTE"
    particle_count = 60
    particle_radius = 2.0
    sound = "BLOCK_NOTE_BLOCK_HARP"
    weather = "clear"
    headline = "城市舆论稳定"

    def _detail_lines(limit: int) -> List[str]:
        highlighted = entries[:limit]
        lines: List[str] = []
        for entry in highlighted:
            marker = {
                "praise": "赞誉",
                "concern": "担忧",
                "controversy": "争议",
                "regulation_proposal": "监管提案",
            }.get(entry.category, entry.category)
            lines.append(f"[{marker}] {entry.title}")
        return lines

    if score >= 0.35 or category_counter.get("praise", 0) > max(category_counter.get("concern", 0), category_counter.get("controversy", 0)):
        mood = "celebration"
        intensity = "high"
        particle = "FIREWORKS_SPARK"
        particle_count = 120
        particle_radius = 3.5
        sound = "ENTITY_PLAYER_LEVELUP"
        weather = "clear"
        headline = "城市洋溢着赞誉"
    elif score >= 0.15:
        mood = "optimistic"
        intensity = "medium"
        particle = "VILLAGER_HAPPY"
        particle_count = 80
        particle_radius = 2.5
        sound = "BLOCK_AMETHYST_BLOCK_HIT"
        weather = "clear"
        headline = "市民保持乐观"
    elif score <= -0.35 or (
        dominant_category in {"controversy", "regulation_proposal"}
        and stress > trust
    ):
        mood = "crisis"
        intensity = "high"
        particle = "ASH"
        particle_count = 120
        particle_radius = 3.2
        sound = "AMBIENT_CAVE"
        weather = "thunder"
        headline = "市民集结表达担忧"
    elif score <= -0.15 or dominant_category == "concern":
        mood = "uneasy"
        intensity = "medium"
        particle = "SMOKE_NORMAL"
        particle_count = 90
        particle_radius = 3.0
        sound = "BLOCK_ANVIL_PLACE"
        weather = "rain"
        headline = "城市弥漫隐忧"

    detail_lines = _detail_lines(highlight_count or 3)

    return SocialAtmosphereEffect(
        mood=mood,
        intensity=intensity,
        particle=particle,
        particle_count=particle_count,
        particle_radius=particle_radius,
        sound=sound,
        weather=weather,
        headline=headline,
        detail_lines=detail_lines,
        dominant_category=dominant_category,
    )
