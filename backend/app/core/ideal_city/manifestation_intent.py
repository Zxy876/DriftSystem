"""Manifestation intent protocol payloads for Ideal City ↔ CrystalTech bridge."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_SCHEMA_VERSION = "0.1.0"
DEFAULT_INTENT_KIND = "CRYSTAL_TECH_STAGE_UNLOCK"
DEFAULT_CONFIDENCE_LEVEL = "research_validated"
DEFAULT_TTL = timedelta(days=1)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ManifestationIntent(BaseModel):
    intent_id: str = Field(default_factory=lambda: uuid4().hex)
    intent_kind: str = Field(default=DEFAULT_INTENT_KIND)
    schema_version: str = Field(default=DEFAULT_SCHEMA_VERSION)
    scenario_id: str
    scenario_version: Optional[str] = None
    allowed_stage: int
    confidence_level: str = Field(default=DEFAULT_CONFIDENCE_LEVEL)
    constraints: List[str] = Field(default_factory=list)
    context_notes: List[str] = Field(default_factory=list)
    issued_at: datetime
    expires_at: datetime
    signature: str = Field(default_factory=lambda: f"ideal-city::{uuid4().hex}")

    model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})

    @classmethod
    def create(
        cls,
        *,
        scenario_id: str,
        allowed_stage: int,
        constraints: List[str],
        context_notes: List[str],
        scenario_version: Optional[str] = None,
        confidence_level: str = DEFAULT_CONFIDENCE_LEVEL,
        ttl: timedelta = DEFAULT_TTL,
        intent_kind: str = DEFAULT_INTENT_KIND,
        intent_id: Optional[str] = None,
    ) -> "ManifestationIntent":
        issued_at = _now_utc()
        expires_at = issued_at + ttl
        return cls(
            intent_id=intent_id or uuid4().hex,
            intent_kind=intent_kind,
            scenario_id=scenario_id,
            scenario_version=scenario_version,
            allowed_stage=allowed_stage,
            confidence_level=confidence_level,
            constraints=list(constraints),
            context_notes=list(context_notes),
            issued_at=issued_at,
            expires_at=expires_at,
        )


class ManifestationIntentQueueEntry(BaseModel):
    intent: ManifestationIntent
    status: str = Field(default="pending")
    queued_at: datetime = Field(default_factory=_now_utc)
    source_spec_id: Optional[str] = Field(default=None, serialization_alias="source_spec_id")

    model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})
