"""Conversation-scoped story state shared between narrative guidance and build pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .build_plan import PlayerPose


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StoryState(BaseModel):
    """Aggregated player intent captured across narrative turns."""

    player_id: str
    scenario_id: str
    goals: List[str] = Field(default_factory=list)
    logic_outline: List[str] = Field(default_factory=list)
    resources: List[str] = Field(default_factory=list)
    community_requirements: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    world_constraints: List[str] = Field(default_factory=list)
    risk_register: List[str] = Field(default_factory=list)
    risk_notes: List[str] = Field(default_factory=list)
    location_hint: Optional[str] = None
    player_pose: Optional[PlayerPose] = None
    notes: List[str] = Field(default_factory=list)
    exhibit_instances: List[str] = Field(default_factory=list)
    ready_for_build: bool = False
    open_questions: List[str] = Field(default_factory=list)
    blocking: List[str] = Field(default_factory=list)
    coverage: Dict[str, bool] = Field(default_factory=dict)
    motivation_score: int = 0
    logic_score: int = 0
    build_capability: int = 0
    last_plan_id: Optional[str] = None
    last_plan_status: Optional[str] = None
    last_plan_synced_at: Optional[datetime] = None
    version: int = 1
    updated_at: datetime = Field(default_factory=_now)

    def bump(self) -> "StoryState":
        """Return a copy with version and timestamp advanced."""

        return self.model_copy(update={"version": self.version + 1, "updated_at": _now()})


class StoryStateEnvelope(BaseModel):
    """Storage wrapper placed on disk for future extensibility."""

    state: StoryState
    frozen_at: datetime = Field(default_factory=_now)


class StoryStatePatch(BaseModel):
    """Sparse update returned by narrative agent before merge."""

    goals: Optional[List[str]] = None
    logic_outline: Optional[List[str]] = None
    resources: Optional[List[str]] = None
    community_requirements: Optional[List[str]] = None
    success_criteria: Optional[List[str]] = None
    world_constraints: Optional[List[str]] = None
    risk_register: Optional[List[str]] = None
    risk_notes: Optional[List[str]] = None
    location_hint: Optional[str] = None
    player_pose: Optional[PlayerPose] = None
    notes: Optional[List[str]] = None
    follow_up_questions: Optional[List[str]] = None
    blocking: Optional[List[str]] = None
    coverage: Optional[Dict[str, bool]] = None
    motivation_score: Optional[int] = None
    logic_score: Optional[int] = None
    build_capability: Optional[int] = None
