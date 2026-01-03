"""Worldview loading utilities for the Ideal City pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_cache_lock = Lock()
_cached_worldview: Optional["WorldviewContext"] = None
_cached_path: Optional[Path] = None


@dataclass(frozen=True)
class WorldviewContext:
    """In-memory representation of the Ideal City worldview."""

    spirit_core: str
    historical_context: Dict[str, Any]
    player_role: Dict[str, Any]
    design_principles: List[str]
    forbidden_patterns: List[str]
    review_questions: List[str]
    response_styles: Dict[str, List[str]]

    def spirit_banner(self) -> str:
        return self.spirit_core

    def follow_up_templates(self) -> List[str]:
        return self.response_styles.get("follow_up", [])

    def rejection_templates(self) -> List[str]:
        return self.response_styles.get("reject", [])

    def affirmation_templates(self) -> List[str]:
        return self.response_styles.get("affirm", [])

    def contextualise(self, scenario_summary: str) -> List[str]:
        """Compose notes combining spirit and scenario summary for notices."""

        notes: List[str] = [f"世界精神：{self.spirit_core}"]
        if scenario_summary:
            notes.append(f"题面语境：{scenario_summary}")
        key_points = self.historical_context.get("touchstones", [])
        if key_points:
            notes.append(f"历史触发点：{key_points[0]}")
        return notes

    def review_prompt(self) -> str:
        if self.review_questions:
            return self.review_questions[0]
        return "请说明你的设计回应了什么社会问题。"


def _resolve_worldview_path() -> Path:
    override = os.getenv("IDEAL_CITY_DATA_ROOT")
    if override:
        return Path(override) / "worldview.json"
    backend_root = Path(__file__).resolve().parents[3]
    return backend_root / "data" / "ideal_city" / "worldview.json"


def load_worldview() -> WorldviewContext:
    """Load worldview data from disk with caching."""

    global _cached_worldview, _cached_path
    path = _resolve_worldview_path()
    with _cache_lock:
        if _cached_worldview is not None and _cached_path == path:
            return _cached_worldview
        if not path.exists():
            raise FileNotFoundError(
                f"Ideal City worldview file missing at {path}."
            )
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        _cached_worldview = WorldviewContext(
            spirit_core=payload.get("spirit_core", ""),
            historical_context=payload.get("historical_context", {}),
            player_role=payload.get("player_role", {}),
            design_principles=payload.get("design_principles", []),
            forbidden_patterns=payload.get("forbidden_patterns", []),
            review_questions=payload.get("review_questions", []),
            response_styles=payload.get("response_styles", {}),
        )
        _cached_path = path
        return _cached_worldview
