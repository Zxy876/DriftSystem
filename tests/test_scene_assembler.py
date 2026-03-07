from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.narrative.scene_assembler import assemble_scene


class SceneAssemblerTest(unittest.TestCase):
    def test_rule_driven_fragments_generate_expected_event_order(self):
        result = assemble_scene(
            {
                "player_id": "vivn",
                "resources": {"wood": 3, "torch": 2, "pork": 1},
                "updated_at_ms": 123,
            },
            "荒野大风",
            anchor_position={"x": 10, "y": 70, "z": -2, "world": "world"},
        )

        self.assertEqual(
            result["scene_plan"]["fragments"],
            ["camp", "fire", "cooking_area"],
        )
        self.assertEqual(
            [event["event_id"] for event in result["event_plan"]],
            ["spawn_camp", "spawn_fire", "spawn_cooking_area"],
        )

        scene_graph = result.get("scene_graph") or {}
        self.assertEqual(scene_graph.get("root"), "camp")
        self.assertEqual(scene_graph.get("nodes"), ["camp", "fire", "cooking_area"])
        self.assertEqual(
            scene_graph.get("edges"),
            [{"from": "camp", "to": "fire"}, {"from": "camp", "to": "cooking_area"}],
        )

        layout = result.get("layout") or {}
        self.assertEqual(layout.get("root"), "camp")
        self.assertTrue(isinstance((layout.get("positions") or {}).get("camp"), dict))

    def test_same_input_is_deterministic(self):
        inventory = {
            "player_id": "p1",
            "resources": {"wood": 1, "torch": 1, "pork": 0},
            "updated_at_ms": 999,
        }
        theme = "夜风"
        anchor = {"x": 5, "y": 64, "z": 5, "world": "world"}

        first = assemble_scene(inventory, theme, anchor_position=anchor)
        second = assemble_scene(inventory, theme, anchor_position=anchor)

        self.assertEqual(first, second)

    def test_anchor_position_is_bound_to_event_anchor(self):
        result = assemble_scene(
            {
                "player_id": "p2",
                "resources": {"wood": 1},
            },
            "",
            anchor_position={"x": 12, "y": 66, "z": -8, "world": "world"},
        )

        self.assertEqual(len(result["event_plan"]), 1)
        anchor = result["event_plan"][0]["anchor"]
        self.assertEqual(anchor.get("mode"), "absolute")
        self.assertEqual(anchor.get("ref"), "player")
        self.assertEqual(anchor.get("world"), "world")
        self.assertEqual(anchor.get("x"), 12.0)
        self.assertEqual(anchor.get("y"), 66.0)
        self.assertEqual(anchor.get("z"), -8.0)

    def test_empty_inputs_produce_empty_event_plan(self):
        result = assemble_scene(None, None, anchor_position=None)

        self.assertEqual(result["scene_plan"]["fragments"], [])
        self.assertEqual(result["event_plan"], [])
        self.assertEqual(result["inventory_state"]["resources"], {})

    def test_branch_camp_chain_deterministic(self):
        inventory = {
            "player_id": "camp_branch",
            "resources": {"wood": 3, "torch": 2, "pork": 1},
            "updated_at_ms": 200,
        }
        first = assemble_scene(
            inventory,
            "荒野大风",
            anchor_position={"x": 2, "y": 64, "z": -1, "world": "world"},
        )
        second = assemble_scene(
            inventory,
            "荒野大风",
            anchor_position={"x": 2, "y": 64, "z": -1, "world": "world"},
        )

        self.assertEqual(first, second)
        fragments = first["scene_plan"]["fragments"]
        self.assertTrue(fragments)
        self.assertEqual(fragments[0], "camp")
        self.assertIn("fire", fragments)
        self.assertIn("cooking_area", fragments)
        self.assertNotIn("wanderer_npc", fragments)
        self.assertEqual(first["event_plan"][0].get("event_id"), "spawn_camp")

    def test_branch_forge_chain_deterministic(self):
        inventory = {
            "player_id": "forge_branch",
            "resources": {"stone": 2, "iron_ingot": 2, "campfire": 1},
            "updated_at_ms": 300,
        }
        first = assemble_scene(
            inventory,
            "",
            anchor_position={"x": 7, "y": 65, "z": 3, "world": "world"},
        )
        second = assemble_scene(
            inventory,
            "",
            anchor_position={"x": 7, "y": 65, "z": 3, "world": "world"},
        )

        self.assertEqual(first, second)
        fragments = first["scene_plan"]["fragments"]
        self.assertTrue(fragments)
        self.assertEqual(fragments[0], "forge")
        self.assertEqual(first["event_plan"][0].get("event_id"), "spawn_forge")

    def test_branch_village_chain_deterministic(self):
        first = assemble_scene(
            {
                "player_id": "village_branch",
                "resources": {
                    "bread": 3,
                    "emerald": 2,
                    "wood": 1,
                    "water_bucket": 1,
                },
                "updated_at_ms": 777,
            },
            "",
            anchor_position={"x": 3, "y": 65, "z": -1, "world": "world"},
        )
        second = assemble_scene(
            {
                "player_id": "village_branch",
                "resources": {
                    "bread": 3,
                    "emerald": 2,
                    "wood": 1,
                    "water_bucket": 1,
                },
                "updated_at_ms": 777,
            },
            "",
            anchor_position={"x": 3, "y": 65, "z": -1, "world": "world"},
        )

        self.assertEqual(first, second)

        fragments = first["scene_plan"]["fragments"]
        self.assertTrue(fragments)
        self.assertEqual(fragments[0], "village")
        self.assertIn("market", fragments)

        event_plan = first["event_plan"]
        self.assertTrue(event_plan)
        self.assertEqual(event_plan[0].get("event_id"), "spawn_village")

    def test_scoring_debug_contains_explainable_fields(self):
        result = assemble_scene(
            {
                "player_id": "debug_branch",
                "resources": {"wood": 2, "torch": 1, "pork": 1},
                "updated_at_ms": 555,
            },
            "大风吹",
            scene_hint="森林",
            anchor_position={"x": 1, "y": 64, "z": 1, "world": "world"},
        )

        scoring = result.get("scoring_debug") or {}
        self.assertTrue(scoring)
        self.assertIn("selected_root", scoring)
        self.assertIn("candidate_scores", scoring)
        self.assertIn("selected_children", scoring)
        self.assertIn("blocked", scoring)
        self.assertIn("reasons", scoring)
        self.assertIn("semantic_scores", scoring)
        self.assertEqual(scoring.get("selected_root"), "camp")

    def test_debug_trace_prints_inventory_and_fragments(self):
        inventory = {
            "player_id": "vivn",
            "resources": {"wood": 1, "torch": 1},
            "updated_at_ms": 321,
        }

        with patch.dict("os.environ", {"DRIFT_DEBUG_TRACE": "true"}, clear=False), patch(
            "app.core.narrative.scene_assembler.logger.info"
        ) as log_mock:
            assemble_scene(
                inventory,
                "大风吹",
                scene_hint="森林",
                anchor_position={"x": 5, "y": 64, "z": 5, "world": "world"},
            )

        self.assertTrue(log_mock.called)
        rendered_lines = [" ".join(str(arg) for arg in call.args) for call in log_mock.call_args_list]
        scene_line = next((line for line in rendered_lines if "[SceneAssembler]" in line), "")
        self.assertTrue(scene_line)
        self.assertIn('"inventory_state"', scene_line)
        self.assertIn('"wood": 1', scene_line)
        self.assertIn('"fragments"', scene_line)
        self.assertIn('"event_ids"', scene_line)

    def test_scene_layout_offsets_are_embedded_in_event_plan(self):
        result = assemble_scene(
            {
                "player_id": "layout_probe",
                "resources": {"wood": 3, "torch": 1, "pork": 1},
                "updated_at_ms": 321,
            },
            "荒野营地",
            anchor_position={"x": 5, "y": 64, "z": 5, "world": "world"},
        )

        offsets = {evt.get("event_id"): (evt.get("offset") or {}) for evt in (result.get("event_plan") or [])}
        self.assertEqual(offsets.get("spawn_camp", {}).get("dx"), 0.0)
        self.assertEqual(offsets.get("spawn_camp", {}).get("dz"), 0.0)

        fire_offset = offsets.get("spawn_fire") or {}
        cooking_offset = offsets.get("spawn_cooking_area") or {}
        self.assertNotEqual((fire_offset.get("dx"), fire_offset.get("dz")), (0.0, 0.0))
        self.assertNotEqual((cooking_offset.get("dx"), cooking_offset.get("dz")), (0.0, 0.0))
        self.assertNotEqual((fire_offset.get("dx"), fire_offset.get("dz")), (cooking_offset.get("dx"), cooking_offset.get("dz")))


if __name__ == "__main__":
    unittest.main()
