"""Scenario loading utilities for Ideal City problem statements."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

def _resolve_scenario_dir() -> Path:
    override = os.getenv("IDEAL_CITY_DATA_ROOT")
    if override:
        return Path(override) / "scenarios"
    backend_root = Path(__file__).resolve().parents[3]
    return backend_root / "data" / "ideal_city" / "scenarios"


@dataclass(frozen=True)
class ScenarioContext:
    scenario_id: str
    title: str
    problem_statement: str
    contextual_constraints: List[str]
    stakeholders: List[str]
    emerging_risks: List[str]
    success_markers: List[str]

    def summary(self) -> str:
        return f"《{self.title}》——{self.problem_statement}"


class ScenarioRepository:
    """Load scenario descriptions from disk on demand."""

    def __init__(self) -> None:
        self._cache: Dict[str, ScenarioContext] = {}
        self._lock = Lock()
        self._scenario_dir = _resolve_scenario_dir()

    def load(self, scenario_id: str) -> ScenarioContext:
        with self._lock:
            cached = self._cache.get(scenario_id)
            if cached is not None:
                return cached
            path = self._scenario_dir / f"{scenario_id}.json"
            if not path.exists():
                raise FileNotFoundError(
                    f"Ideal City scenario '{scenario_id}' missing at {path}."
                )
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            context = ScenarioContext(
                scenario_id=payload.get("scenario_id", scenario_id),
                title=payload.get("title", scenario_id),
                problem_statement=payload.get("problem_statement", ""),
                contextual_constraints=payload.get("contextual_constraints", []),
                stakeholders=payload.get("stakeholders", []),
                emerging_risks=payload.get("emerging_risks", []),
                success_markers=payload.get("success_markers", []),
            )
            self._cache[scenario_id] = context
            return context

    def available(self) -> List[str]:
        return [path.stem for path in self._scenario_dir.glob("*.json")]
