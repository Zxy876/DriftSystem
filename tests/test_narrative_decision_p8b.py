from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.api import world_api
from app.core.story.narrative_decision import choose_transition
from app.core.story.narrative_transition_log import NarrativeTransitionLogStore


def _state_with_candidates(*, current_node: str, candidates: list[dict], observed_signals: list[str] | None = None) -> dict:
    return {
        "version": "narrative_state_v1",
        "graph_version": "p8a_v1",
        "current_arc": "main",
        "current_node": current_node,
        "unlocked_nodes": [current_node],
        "completed_nodes": [],
        "transition_candidates": list(candidates),
        "blocked_by": [],
        "observed_signals": list(observed_signals or []),
    }


class NarrativeDecisionP8BTest(unittest.TestCase):
    def test_choose_transition_is_deterministic(self):
        narrative_state = _state_with_candidates(
            current_node="camp_life",
            observed_signals=["scene:camp", "collect:oak_log", "level_stage:camp"],
            candidates=[
                {
                    "node": "village_arrival",
                    "requires": ["scene:camp", "collect:oak_log"],
                    "blocked_by": [],
                    "satisfied": True,
                    "priority": 3,
                },
                {
                    "node": "watchtower_arc",
                    "requires": ["scene:camp"],
                    "blocked_by": [],
                    "satisfied": True,
                    "priority": 3,
                },
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            store = NarrativeTransitionLogStore(base_dir=temp_dir)
            first = choose_transition("vivn", narrative_state=narrative_state, transition_log_store=store)
            second = choose_transition("vivn", narrative_state=narrative_state, transition_log_store=store)

        self.assertEqual(
            (first.get("decision") or {}).get("chosen_transition"),
            (second.get("decision") or {}).get("chosen_transition"),
        )
        self.assertEqual(
            (first.get("decision") or {}).get("target_node"),
            (second.get("decision") or {}).get("target_node"),
        )

    def test_blocked_transition_is_not_selected(self):
        narrative_state = _state_with_candidates(
            current_node="camp_life",
            observed_signals=["scene:camp"],
            candidates=[
                {
                    "node": "village_arrival",
                    "requires": ["scene:village"],
                    "blocked_by": ["scene:village"],
                    "satisfied": False,
                    "priority": 9,
                },
                {
                    "node": "watchtower_arc",
                    "requires": ["scene:camp"],
                    "blocked_by": [],
                    "satisfied": True,
                    "priority": 1,
                },
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = choose_transition(
                "vivn",
                narrative_state=narrative_state,
                transition_log_store=NarrativeTransitionLogStore(base_dir=temp_dir),
            )

        decision = result.get("decision") or {}
        self.assertEqual(decision.get("target_node"), "watchtower_arc")
        self.assertNotEqual(decision.get("target_node"), "village_arrival")

    def test_tie_break_is_lexicographically_stable(self):
        narrative_state = _state_with_candidates(
            current_node="camp_life",
            observed_signals=["scene:camp"],
            candidates=[
                {
                    "node": "beta_arc",
                    "requires": ["scene:camp"],
                    "blocked_by": [],
                    "satisfied": True,
                    "priority": 5,
                },
                {
                    "node": "alpha_arc",
                    "requires": ["scene:camp"],
                    "blocked_by": [],
                    "satisfied": True,
                    "priority": 5,
                },
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = choose_transition(
                "vivn",
                narrative_state=narrative_state,
                transition_log_store=NarrativeTransitionLogStore(base_dir=temp_dir),
            )

        decision = result.get("decision") or {}
        self.assertEqual(decision.get("target_node"), "alpha_arc")

    def test_decision_updates_current_node(self):
        narrative_state = _state_with_candidates(
            current_node="camp_life",
            observed_signals=["scene:camp"],
            candidates=[
                {
                    "node": "watchtower_arc",
                    "requires": ["scene:camp"],
                    "blocked_by": [],
                    "satisfied": True,
                    "priority": 1,
                }
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = choose_transition(
                "vivn",
                narrative_state=narrative_state,
                transition_log_store=NarrativeTransitionLogStore(base_dir=temp_dir),
            )

        updated_state = result.get("narrative_state") or {}
        self.assertEqual(updated_state.get("current_node"), "watchtower_arc")
        self.assertIn("camp_life", updated_state.get("completed_nodes") or [])

    def test_world_api_choose_endpoint_requires_explicit_call_and_no_world_patch(self):
        level_obj = SimpleNamespace(meta={}, _raw_payload={"meta": {}})
        narrative_state = _state_with_candidates(
            current_node="camp_life",
            observed_signals=["scene:camp"],
            candidates=[
                {
                    "node": "watchtower_arc",
                    "requires": ["scene:camp"],
                    "blocked_by": [],
                    "satisfied": True,
                    "priority": 1,
                }
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_store = NarrativeTransitionLogStore(base_dir=temp_dir)
            with patch("app.api.world_api._scene_level_for_player", return_value=level_obj), patch(
                "app.api.world_api._scene_generation_for_player",
                return_value={
                    "selected_assets": ["camp"],
                    "asset_selection": {"candidate_assets": ["camp"]},
                    "theme_filter": {"theme": "camp", "applied": False, "allowed_fragments": ["camp"]},
                },
            ), patch(
                "app.api.world_api.quest_runtime.get_debug_snapshot",
                return_value={
                    "level_state": {"current_stage": "camp", "stage_path": ["forest", "camp"]},
                    "recent_rule_events": [{"event_type": "collect", "payload": {"item_type": "oak_log"}}],
                },
            ), patch(
                "app.api.world_api.story_engine.get_public_state",
                return_value={"player_current_level": "flagship_01"},
            ), patch(
                "app.api.world_api._narrative_state_for_player",
                return_value=narrative_state,
            ), patch(
                "app.core.story.narrative_decision.narrative_transition_log_store",
                temp_store,
            ):
                response = world_api.story_narrative_choose(
                    "vivn",
                    payload=world_api.NarrativeChooseRequest(mode="auto_best"),
                )

        self.assertEqual(response.get("status"), "ok")
        self.assertIsNone(response.get("world_patch"))
        self.assertIn("narrative_decision", response)
        self.assertTrue((response.get("narrative_decision") or {}).get("chosen_transition"))


if __name__ == "__main__":
    unittest.main()
