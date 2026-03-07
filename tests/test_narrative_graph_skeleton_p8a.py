from __future__ import annotations

import sys
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
from app.core.story.narrative_graph_evaluator import evaluate_narrative_state


class NarrativeGraphSkeletonP8ATest(unittest.TestCase):
    def test_evaluator_returns_blocked_transition_when_requirements_missing(self):
        narrative_state = evaluate_narrative_state(
            level_state={"current_stage": "camp", "stage_path": ["forest", "camp"]},
            scene_generation={
                "scene_state": {"root": "camp", "nodes": ["camp", "fire", "cooking_area"]},
                "scene_graph": {"root": "camp", "nodes": ["camp", "fire", "cooking_area"]},
            },
            recent_rule_events=[{"event_type": "collect", "payload": {"item_type": "oak_log", "amount": 1}}],
        )

        self.assertEqual(narrative_state.get("version"), "narrative_state_v1")
        self.assertEqual(narrative_state.get("current_node"), "forest_intro")

        candidates = narrative_state.get("transition_candidates") or []
        self.assertTrue(candidates)
        self.assertEqual(candidates[0].get("node"), "camp_life")
        self.assertFalse(candidates[0].get("satisfied"))
        self.assertIn("scene:village", candidates[0].get("blocked_by") or [])

        self.assertIn("scene:village", narrative_state.get("blocked_by") or [])

    def test_evaluator_returns_satisfied_transition_when_village_signal_present(self):
        narrative_state = evaluate_narrative_state(
            level_state={"current_stage": "camp", "stage_path": ["forest", "camp"]},
            scene_generation={
                "scene_state": {"root": "village", "nodes": ["camp", "village", "farm"]},
                "scene_graph": {"root": "village", "nodes": ["camp", "village", "farm"]},
            },
            recent_rule_events=[{"event_type": "collect", "payload": {"item_type": "bread", "amount": 1}}],
        )

        candidates = narrative_state.get("transition_candidates") or []
        self.assertTrue(candidates)
        self.assertEqual(candidates[0].get("node"), "camp_life")
        self.assertTrue(candidates[0].get("satisfied"))
        self.assertEqual(candidates[0].get("blocked_by"), [])

    def test_world_state_exposes_narrative_fields(self):
        with patch("app.api.world_api.story_engine.get_public_state", return_value={"player_current_level": "flagship_01"}), patch(
            "app.api.world_api.world_engine.get_state",
            return_value={"variables": {"x": 1}, "entities": {}},
        ), patch(
            "app.api.world_api.quest_runtime.get_debug_snapshot",
            return_value={
                "level_state": {"current_stage": "camp", "stage_path": ["forest", "camp"]},
                "recent_rule_events": [],
            },
        ), patch(
            "app.api.world_api._scene_generation_for_player",
            return_value={"scene_state": {"root": "camp", "nodes": ["camp"]}},
        ):
            response = world_api.world_state("vivn")

        self.assertEqual(response.get("status"), "ok")
        self.assertIn("narrative_state", response)
        self.assertIn("current_node", response)
        self.assertIn("transition_candidates", response)
        self.assertIn("blocked_by", response)
        self.assertEqual((response.get("narrative_state") or {}).get("current_node"), response.get("current_node"))

    def test_eventdebug_exposes_narrative_fields_without_active_task_state(self):
        fake_request = SimpleNamespace(headers={})

        with patch("app.api.world_api.quest_runtime.get_debug_snapshot", return_value=None), patch(
            "app.api.world_api._scene_generation_for_player",
            return_value={"scene_state": {"root": "camp", "nodes": ["camp"]}},
        ):
            response = world_api.story_debug_tasks("vivn", request=fake_request, token=None)

        self.assertEqual(response.get("status"), "error")
        self.assertIn("narrative_state", response)
        self.assertIn("current_node", response)
        self.assertIn("transition_candidates", response)
        self.assertIn("blocked_by", response)


if __name__ == "__main__":
    unittest.main()
