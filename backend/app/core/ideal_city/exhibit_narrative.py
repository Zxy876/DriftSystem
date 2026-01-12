"""Structured curatorial narrative definitions for CityPhone exhibits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ExhibitNarrative(BaseModel):
    """Curated narrative slices surfaced by CityPhone."""

    scenario_id: str
    title: Optional[str] = None
    timeframe: Optional[str] = None
    mode: Optional[str] = None
    archive_state: List[str] = Field(default_factory=list)
    unresolved_risks: List[str] = Field(default_factory=list)
    historic_notes: List[str] = Field(default_factory=list)
    city_interpretation: List[str] = Field(default_factory=list)
    appendix: Dict[str, List[str]] = Field(default_factory=dict)


class ExhibitNarrativeRepository:
    """Filesystem-backed repository for precomposed exhibit narratives."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def load(self, scenario_id: str) -> ExhibitNarrative:
        path = self._root / f"{scenario_id}.json"
        if not path.exists():
            return ExhibitNarrative(scenario_id=scenario_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ExhibitNarrative(scenario_id=scenario_id)
        if not isinstance(payload, dict):
            return ExhibitNarrative(scenario_id=scenario_id)
        payload.setdefault("scenario_id", scenario_id)
        try:
            return ExhibitNarrative.model_validate(payload)
        except Exception:
            # Fallback to a minimal stub if validation fails so that CityPhone
            # continues to respond with a soft narrative baseline.
            return ExhibitNarrative(
                scenario_id=scenario_id,
                title=str(payload.get("title") or "").strip() or None,
                timeframe=str(payload.get("timeframe") or "").strip() or None,
                mode=str(payload.get("mode") or "").strip() or None,
            )

    def save(self, narrative: ExhibitNarrative) -> Path:
        path = self._root / f"{narrative.scenario_id}.json"
        path.write_text(
            narrative.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path
