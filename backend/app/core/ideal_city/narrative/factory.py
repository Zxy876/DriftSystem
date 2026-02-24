from __future__ import annotations

from typing import Protocol

from app.core.ideal_city.story_state import StoryStatePatch

from .ideal_city_engine import IdealCityNarrativeEngine
from .modes import NarrativeMode
from .reunion_engine import ReunionNarrativeEngine
from .types import NarrativeRuntimeContext


class NarrativeEngine(Protocol):
    def infer(self, context: NarrativeRuntimeContext) -> StoryStatePatch:
        ...


class NarrativeEngineFactory:
    @staticmethod
    def create(mode: NarrativeMode) -> NarrativeEngine:
        if mode is NarrativeMode.REUNION:
            return ReunionNarrativeEngine()
        if mode is NarrativeMode.IDEAL_CITY:
            return IdealCityNarrativeEngine()
        raise ValueError(f"Narrative mode is not supported for production use: {mode.value}")
