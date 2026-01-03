"""World-sovereign adjudication contract for Ideal City.

No natural language inputs, world patch calls, nor plugin hooks live here.
The types below only express the Accept/Partial/Reject envelope and helper
utilities for signed decisions. Algorithmic scoring, task fallbacks, and
presentation logic remain explicitly out of scope to honour all guardrails.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class VerdictEnum(str, Enum):
	ACCEPT = "ACCEPT"
	PARTIAL = "PARTIAL"
	REJECT = "REJECT"
	REVIEW_REQUIRED = "REVIEW_REQUIRED"


class AdjudicationRecord(BaseModel):
	ruling_id: str = Field(default_factory=lambda: uuid4().hex)
	device_spec_id: str
	verdict: VerdictEnum
	reasoning: List[str] = Field(default_factory=list)
	conditions: List[str] = Field(default_factory=list)
	memory_hooks: List[str] = Field(default_factory=list)
	timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
	record_signature: str = Field(default_factory=lambda: f"ideal-city::{uuid4().hex}")

	model_config = ConfigDict(ser_json_encoders={datetime: lambda value: value.isoformat()})


def freeze_for_history(record: AdjudicationRecord) -> dict:
	"""Produce an append-only snapshot for archival storage."""

	payload = record.model_dump(mode="json")
	payload["snapshot_id"] = uuid4().hex
	payload["frozen_at"] = datetime.now(timezone.utc).isoformat()
	return payload
