"""Shared helpers for determining story-state progression phases."""

from __future__ import annotations

from .story_state import StoryState


def determine_phase(state: StoryState) -> str:
    """Return the conversational phase for the given story state."""

    logic_filled = len([item for item in state.logic_outline if item.strip()]) >= 2
    constraints_ready = bool([item for item in state.world_constraints if item and item.strip()])
    if not logic_filled or not state.goals or not constraints_ready:
        return "vision"
    if not state.resources or not state.success_criteria or not state.risk_register:
        return "resources"
    if state.player_pose is None or not state.location_hint:
        return "location"
    return "wrap"
