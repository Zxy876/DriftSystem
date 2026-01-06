"""Execution notices derived from adjudication outputs.

Nothing here triggers Minecraft actions directly; it only prepares structured
payloads that downstream presenters (text panels, HUDs, logs) may consume after
adjudication signs a verdict. The zero-mod guarantee is preserved by keeping
data rendering-agnostic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .adjudication_contract import AdjudicationRecord, VerdictEnum
from .build_plan import PlayerPose


class PlanLocation(BaseModel):
	world: str
	x: float
	y: float
	z: float


class BuildPlanSnapshot(BaseModel):
	plan_id: Optional[str] = None
	summary: Optional[str] = None
	steps: List[str] = Field(default_factory=list)
	mod_hooks: List[str] = Field(default_factory=list)
	player_pose: Optional[PlayerPose] = None
	location_hint: Optional[PlanLocation] = None


class BroadcastSnapshot(BaseModel):
	title: Optional[str] = None
	spoken: List[str] = Field(default_factory=list)
	call_to_action: Optional[str] = None


class ExecutionNotice(BaseModel):
	notice_id: str = Field(default_factory=lambda: uuid4().hex)
	player_ref: str
	spec_id: str
	verdict: VerdictEnum
	headline: str
	body: List[str] = Field(default_factory=list)
	guidance: List[str] = Field(default_factory=list)
	build_plan: Optional[BuildPlanSnapshot] = None
	broadcast: Optional[BroadcastSnapshot] = None
	created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

	model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})


def build_notice(
	player_ref: str,
	spec_id: str,
	record: AdjudicationRecord,
	context_notes: Optional[List[str]] = None,
	guidance: Optional[List[str]] = None,
	build_plan: Optional[BuildPlanSnapshot] = None,
	broadcast: Optional[BroadcastSnapshot] = None,
) -> ExecutionNotice:
	"""Translate a signed adjudication record into a presentation-safe notice."""

	headline = f"Ideal City verdict: {record.verdict.value}"
	body: List[str] = []

	if record.reasoning:
		body.extend(record.reasoning)
	if record.conditions:
		body.append("Follow-up conditions:")
		body.extend(f" - {item}" for item in record.conditions)
	if context_notes:
		body.append("Context cues:")
		body.extend(f" ~ {note}" for note in context_notes)

	return ExecutionNotice(
		player_ref=player_ref,
		spec_id=spec_id,
		verdict=record.verdict,
		headline=headline,
		body=body,
		guidance=guidance or [],
		build_plan=build_plan,
		broadcast=broadcast,
	)
