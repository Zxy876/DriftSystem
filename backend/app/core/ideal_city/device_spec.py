"""DeviceSpec domain model for Ideal City submissions.

This module keeps the DeviceSpec object isolated from task/story constructs,
aligning with docs/IDEAL_CITY_ENGINEERING_LANGUAGE.md and
docs/IDEAL_CITY_EXECUTION_GUARDRAILS.md. It deliberately avoids importing
gameplay runners, world patch emitters, or legacy Kunming Lake/Xinyue
schemas. All helpers below remain side-effect free; they shape data but never
mutate world state nor trigger adjudication.

Execution guardrail alignment:
- ✅ DeviceSpec first-class object: strongly typed, serialisable structure for
	civic proposals.
- ✅ Pure handoff pipeline: contains helper to pack audit metadata without
	touching adjudication logic.
- 🚫 Prohibited duties: no natural language parsing, no backend routing, no
	Minecraft command emission.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

# COMPLETED[CEC-STRUCTURE-01][阶段: 概念补齐]
# Schema for captured proposal semantics. All fields intentionally qualitative
# and narrative facing; no numeric scoring or execution hooks are present.


class DeviceSpec(BaseModel):
    spec_id: str = Field(default_factory=lambda: uuid4().hex)
    author_ref: str
    intent_summary: str
    scenario_id: str = Field(default="default")
    is_draft: bool = False
    world_constraints: List[str] = Field(default_factory=list)
    logic_outline: List[str] = Field(default_factory=list)
    resource_ledger: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    risk_register: List[str] = Field(default_factory=list)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_narrative: str = ""

    model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})


# COMPLETED[CEC-STRUCTURE-02][阶段: 接口占位]
# Lightweight envelope that can accompany queue transport without altering
# world state. Audit-only metadata lives here.


class DeviceSpecEnvelope(BaseModel):
    spec: DeviceSpec
    submitted_by_session: Optional[str] = None
    transport_trace: List[str] = Field(default_factory=list)
    audit_token: str = Field(default_factory=lambda: uuid4().hex)


# COMPLETED[CEC-GOVERNANCE-01][阶段: 概念补齐]
# Helper to create immutable history entries for archival storage.


def freeze_for_history(spec: DeviceSpec) -> dict:
    """Return a pure dict snapshot suitable for append-only storage."""

    payload = spec.model_dump(mode="json")
    payload["snapshot_id"] = uuid4().hex
    payload["frozen_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def sanitize_lines(values: Optional[List[str]]) -> List[str]:
    """Strip whitespace from narrative lists while keeping ordering."""

    if not values:
        return []
    return [item.strip() for item in values if item and item.strip()]
