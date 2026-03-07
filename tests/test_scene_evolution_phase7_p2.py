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

from app.api import story_api, world_api
from app.core.narrative.scene_evolution import evolve_scene_state
from app.core.narrative.scene_state import SceneState


class SceneEvolutionPhase7P2Test(unittest.TestCase):
    @staticmethod
    def _camp_state() -> SceneState:
        return SceneState.from_scene_payload(
            level_id="phase7_camp",
            scene_graph={
                "root": "camp",
                "nodes": ["camp", "fire", "cooking_area"],
                "edges": [
                    {"from": "camp", "to": "fire"},
                    {"from": "camp", "to": "cooking_area"},
                ],
            },
            layout={
                "root": "camp",
                "positions": {
                    "camp": {"x": 0, "z": 0},
                    "fire": {"x": 4, "z": 0},
                    "cooking_area": {"x": 0, "z": 4},
                },
            },
            spawned_nodes=["camp", "fire", "cooking_area"],
            version=1,
        )

    @staticmethod
    def _village_state() -> SceneState:
        return SceneState.from_scene_payload(
            level_id="phase7_village",
            scene_graph={
                "root": "village",
                "nodes": ["village", "market"],
                "edges": [{"from": "village", "to": "market"}],
            },
            layout={
                "root": "village",
                "positions": {
                    "village": {"x": 0, "z": 0},
                    "market": {"x": 4, "z": 0},
                },
            },
            spawned_nodes=["village", "market"],
            version=1,
        )

    def test_camp_collect_chain_generates_watchtower_and_road(self):
        result = evolve_scene_state(
            scene_state=self._camp_state(),
            rule_events=[
                {"event_type": "collect", "payload": {"item_type": "oak_log", "amount": 1}},
                {"event_type": "collect", "payload": {"item_type": "stone", "amount": 1}},
            ],
            scene_hint="森林",
            anchor_position={"world": "world", "x": 10, "y": 64, "z": 10},
        )

        scene_state = result["scene_state"]
        scene_diff = result["scene_diff"].to_dict()
        incremental_events = result.get("incremental_event_plan") or []

        self.assertEqual(scene_state.level_id, "phase7_camp")
        self.assertEqual(scene_state.root, "camp")
        self.assertEqual(scene_state.version, 2)

        self.assertIn("watchtower", scene_diff.get("added_nodes") or [])
        self.assertIn("road", scene_diff.get("added_nodes") or [])
        self.assertIn("watchtower", scene_diff.get("added_positions") or {})
        self.assertIn("road", scene_diff.get("added_positions") or {})

        event_ids = [row.get("event_id") for row in incremental_events if isinstance(row, dict)]
        self.assertIn("spawn_watchtower", event_ids)
        self.assertIn("spawn_road", event_ids)

    def test_village_collect_chain_is_deterministic_and_semantic(self):
        events = [
            {"event_type": "collect", "payload": {"item_type": "bread", "amount": 1}},
            {"event_type": "collect", "payload": {"item_type": "iron_ingot", "amount": 1}},
        ]

        first = evolve_scene_state(
            scene_state=self._village_state(),
            rule_events=events,
            scene_hint=None,
            anchor_position={"world": "world", "x": 0, "y": 64, "z": 0},
        )
        second = evolve_scene_state(
            scene_state=self._village_state(),
            rule_events=events,
            scene_hint=None,
            anchor_position={"world": "world", "x": 0, "y": 64, "z": 0},
        )

        first_diff = first["scene_diff"].to_dict()
        second_diff = second["scene_diff"].to_dict()

        self.assertEqual(first_diff, second_diff)
        self.assertEqual(first.get("incremental_event_plan"), second.get("incremental_event_plan"))

        added_nodes = set(first_diff.get("added_nodes") or [])
        self.assertIn("farm", added_nodes)
        self.assertIn("forge", added_nodes)

        trigger_keys = set(first_diff.get("trigger_event_keys") or [])
        self.assertIn("collect:food", trigger_keys)
        self.assertIn("collect:metal", trigger_keys)

    def test_build_scene_events_outputs_scene_state_and_scene_diff_incremental(self):
        fixed_anchor = (
            "home",
            {"world": "world", "x": 3.0, "y": 64.0, "z": -1.0},
            None,
            {"world": "world", "x": 3.0, "y": 64.0, "z": -1.0},
            "home",
        )

        with patch("app.api.story_api._scene_anchor_position_for_inject", return_value=fixed_anchor), patch(
            "app.api.story_api._scene_inventory_state_from_event_log",
            return_value={
                "player_id": "vivn",
                "resources": {"wood": 2, "torch": 1, "pork": 1},
                "updated_at_ms": 1,
            },
        ):
            result = story_api.build_scene_events(
                player_id="vivn",
                scene_theme="荒野大风",
                scene_hint="森林",
                text="创建剧情 荒野大风",
                anchor="home",
                level_id="phase7_inject",
                patch_mode="incremental",
                rule_events=[{"event_type": "collect", "payload": {"item_type": "stone", "amount": 1}}],
            )

        self.assertEqual(result.get("patch_mode"), "incremental")

        scene_state = result.get("scene_state") or {}
        scene_diff = result.get("scene_diff") or {}

        self.assertEqual(scene_state.get("level_id"), "phase7_inject")
        self.assertEqual(scene_state.get("root"), "camp")
        self.assertIn("road", scene_state.get("nodes") or [])
        self.assertIn("road", scene_diff.get("added_nodes") or [])

        incremental_events = result.get("incremental_event_plan") or []
        self.assertTrue(incremental_events)
        event_ids = [row.get("event_id") for row in incremental_events if isinstance(row, dict)]
        self.assertIn("spawn_road", event_ids)

    def test_story_rule_event_merges_incremental_scene_world_patch(self):
        event = world_api.RuleTriggerEvent(
            player_id="vivn",
            event_type="collect",
            payload={"item_type": "stone", "amount": 1},
        )

        quest_result = {
            "world_patch": {
                "mc": {
                    "build_multi": [
                        {"shape": "line", "size": 1, "material": "TORCH"},
                    ]
                }
            }
        }
        scene_result = {
            "scene_world_patch": {
                "mc": {
                    "blocks": [
                        {"type": "campfire", "offset": {"dx": 1, "dy": 0, "dz": 1}},
                    ]
                }
            },
            "scene_diff": {"added_nodes": ["road"]},
        }

        with patch("app.api.world_api._as_bool_env", return_value=False), patch(
            "app.api.world_api.quest_runtime.handle_rule_trigger",
            return_value=quest_result,
        ), patch(
            "app.api.world_api.story_engine.apply_quest_updates",
            return_value=None,
        ), patch(
            "app.api.story_api.evolve_scene_for_rule_event",
            return_value=scene_result,
        ):
            result = world_api.story_rule_event(event)

        self.assertEqual(result.get("status"), "ok")
        self.assertEqual((result.get("scene_diff") or {}).get("added_nodes"), ["road"])

        mc_patch = (result.get("world_patch") or {}).get("mc") or {}
        self.assertEqual(len(mc_patch.get("build_multi") or []), 1)
        self.assertEqual(len(mc_patch.get("blocks") or []), 1)

    def test_eventdebug_exposes_scene_state_and_scene_diff(self):
        level = SimpleNamespace(
            meta={
                "scene_generation": {
                    "scene_state": {"level_id": "flagship_01", "root": "camp", "nodes": ["camp"]},
                    "scene_diff": {"added_nodes": ["watchtower"]},
                }
            }
        )

        players_state = {"vivn": {"level": level}}
        fake_request = SimpleNamespace(headers={})

        with patch.object(world_api.quest_runtime, "_players", players_state, create=True), patch(
            "app.api.world_api.quest_runtime.get_debug_snapshot",
            return_value={"active_tasks": []},
        ):
            result = world_api.story_debug_tasks("vivn", request=fake_request, token=None)

        self.assertEqual(result.get("status"), "ok")
        scene_generation = result.get("scene_generation") or {}
        self.assertEqual((scene_generation.get("scene_state") or {}).get("root"), "camp")
        self.assertEqual((scene_generation.get("scene_diff") or {}).get("added_nodes"), ["watchtower"])


if __name__ == "__main__":
    unittest.main()
