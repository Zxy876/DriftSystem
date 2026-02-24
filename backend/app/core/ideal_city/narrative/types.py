from __future__ import annotations

from dataclasses import dataclass

from app.core.ideal_city.device_spec import DeviceSpec
from app.core.ideal_city.scenario_repository import ScenarioContext
from app.core.ideal_city.story_state import StoryState


@dataclass
class NarrativeRuntimeContext:
    narrative: str
    spec: DeviceSpec
    scenario: ScenarioContext
    existing_state: StoryState
