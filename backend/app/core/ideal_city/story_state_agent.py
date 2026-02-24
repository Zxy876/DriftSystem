"""Narrative agent façade selecting isolated engine implementation by explicit mode."""

from __future__ import annotations

from dataclasses import dataclass

from .device_spec import DeviceSpec
from .narrative import ACTIVE_NARRATIVE_MODE, NarrativeEngineFactory, NarrativeRuntimeContext
from .scenario_repository import ScenarioContext
from .story_state import StoryState, StoryStatePatch


@dataclass
class StoryStateAgentContext:
    narrative: str
    spec: DeviceSpec
    scenario: ScenarioContext
    existing_state: StoryState


class StoryStateAgent:
    """Mode-routed agent wrapper; prompt logic lives in isolated narrative engines."""

    def __init__(self) -> None:
        self._mode = ACTIVE_NARRATIVE_MODE
        self._engine = NarrativeEngineFactory.create(self._mode)

    def infer(self, ctx: StoryStateAgentContext) -> StoryStatePatch:
        runtime_context = NarrativeRuntimeContext(
            narrative=ctx.narrative,
            spec=ctx.spec,
            scenario=ctx.scenario,
            existing_state=ctx.existing_state,
        )
        return self._engine.infer(runtime_context)
