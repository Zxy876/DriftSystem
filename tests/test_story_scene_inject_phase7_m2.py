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

from app.api import story_api


class StorySceneInjectPhase7M2Test(unittest.TestCase):
    def test_scene_resources_prefers_persisted_inventory(self):
        with patch("app.core.quest.runtime.quest_runtime.get_inventory_resources", return_value={"wood": 5, "torch": 3}), patch(
            "app.core.quest.runtime.quest_runtime.get_recent_rule_events",
            return_value=[
                {
                    "raw_payload": {"event_type": "collect", "payload": {"item_type": "wood", "count": 1}},
                    "event": {"event_type": "collect"},
                }
            ],
        ), patch(
            "app.core.quest.runtime.quest_runtime.get_debug_snapshot",
            return_value=None,
        ), patch(
            "app.core.quest.runtime.quest_runtime._players",
            {},
        ):
            resources = story_api._scene_resources_from_recent_rule_events("vivn")

        self.assertEqual(resources, {"wood": 5, "torch": 3})

    def test_scene_resources_reads_detached_rule_event_history(self):
        recent_rows = [
            {
                "raw_payload": {"event_type": "collect", "payload": {"item_type": "wood", "count": 1}},
                "event": {"event_type": "collect"},
            },
            {
                "raw_payload": {"event_type": "collect", "payload": {"resource": "torch", "amount": 2}},
                "event": {"event_type": "collect"},
            },
        ]

        with patch("app.core.quest.runtime.quest_runtime.get_inventory_resources", return_value={}), patch(
            "app.core.quest.runtime.quest_runtime.get_recent_rule_events",
            return_value=recent_rows,
        ), patch(
            "app.core.quest.runtime.quest_runtime.get_debug_snapshot",
            return_value=None,
        ), patch(
            "app.core.quest.runtime.quest_runtime._players",
            {},
        ):
            resources = story_api._scene_resources_from_recent_rule_events("vivn")

        self.assertEqual(resources, {"wood": 1, "torch": 2})

    def test_scene_resources_from_recent_collect_events(self):
        snapshot = {
            "recent_rule_events": [
                {
                    "raw_payload": {"event_type": "collect", "payload": {"item_type": "wood", "count": 2}},
                    "event": {"event_type": "collect"},
                },
                {
                    "raw_payload": {"event_type": "collect", "payload": {"resource": "torch", "amount": 1}},
                    "event": {"event_type": "collect"},
                },
                {
                    "raw_payload": {"event_type": "chat", "payload": {"text": "hi"}},
                    "event": {"event_type": "chat"},
                },
            ]
        }

        with patch("app.core.quest.runtime.quest_runtime.get_inventory_resources", return_value={}), patch(
            "app.core.quest.runtime.quest_runtime.get_debug_snapshot",
            return_value=snapshot,
        ), patch(
            "app.core.quest.runtime.quest_runtime._players",
            {},
        ):
            resources = story_api._scene_resources_from_recent_rule_events("vivn")

        self.assertEqual(resources, {"wood": 2, "torch": 1})

    def test_scene_resources_fallback_to_state_rule_events(self):
        snapshot = {"recent_rule_events": []}
        players_state = {
            "vivn": {
                "rule_events": [
                    {
                        "event_type": "quest_event",
                        "quest_event": "collect_wood",
                        "meta": {"resource": "wood", "amount": 2},
                    },
                    {
                        "event_type": "quest_event",
                        "quest_event": "collect_torch",
                        "meta": {"item_type": "torch", "count": 1},
                    },
                    {
                        "event_type": "quest_event",
                        "quest_event": "collect_pork",
                        "meta": {"item": "pork"},
                    },
                ]
            }
        }

        with patch("app.core.quest.runtime.quest_runtime.get_inventory_resources", return_value={}), patch(
            "app.core.quest.runtime.quest_runtime.get_debug_snapshot",
            return_value=snapshot,
        ), patch(
            "app.core.quest.runtime.quest_runtime._players",
            players_state,
        ):
            resources = story_api._scene_resources_from_recent_rule_events("vivn")

        self.assertEqual(resources, {"wood": 2, "torch": 1, "pork": 1})

    def test_scene_resources_canonicalizes_persisted_inventory_aliases(self):
        with patch(
            "app.core.quest.runtime.quest_runtime.get_inventory_resources",
            return_value={"oak_log": 2, "wood": 1, "raw_porkchop": 1, "cooked_porkchop": 2},
        ), patch(
            "app.core.quest.runtime.quest_runtime.get_recent_rule_events",
            return_value=[],
        ), patch(
            "app.core.quest.runtime.quest_runtime.get_debug_snapshot",
            return_value=None,
        ), patch(
            "app.core.quest.runtime.quest_runtime._players",
            {},
        ):
            resources = story_api._scene_resources_from_recent_rule_events("vivn")

        self.assertEqual(resources, {"wood": 3, "pork": 3})

    def test_scene_resources_canonicalizes_recent_collect_aliases(self):
        recent_rows = [
            {
                "raw_payload": {"event_type": "collect", "payload": {"item_type": "spruce_log", "count": 2}},
                "event": {"event_type": "collect"},
            },
            {
                "raw_payload": {"event_type": "collect", "payload": {"item_type": "cooked_porkchop", "amount": 1}},
                "event": {"event_type": "collect"},
            },
        ]

        with patch("app.core.quest.runtime.quest_runtime.get_inventory_resources", return_value={}), patch(
            "app.core.quest.runtime.quest_runtime.get_recent_rule_events",
            return_value=recent_rows,
        ), patch(
            "app.core.quest.runtime.quest_runtime.get_debug_snapshot",
            return_value=None,
        ), patch(
            "app.core.quest.runtime.quest_runtime._players",
            {},
        ):
            resources = story_api._scene_resources_from_recent_rule_events("vivn")

        self.assertEqual(resources, {"wood": 2, "pork": 1})

    def test_scene_anchor_uses_safe_ground_from_recent_block_interact(self):
        recent_rows = [
            {
                "timestamp": 1700000100,
                "raw_payload": {
                    "event_type": "interact_block",
                    "payload": {
                        "block_type": "grass_block",
                        "location": {"world": "world", "x": 12.2, "y": 64.0, "z": -7.8},
                    },
                },
            }
        ]

        with patch("app.api.story_api._collect_rule_event_rows", return_value=recent_rows), patch.dict(
            "os.environ",
            {
                "DRIFT_ENABLE_SAFE_GROUND_ANCHOR": "true",
                "DRIFT_FIXED_ANCHOR_X": "0",
                "DRIFT_FIXED_ANCHOR_Y": "64",
                "DRIFT_FIXED_ANCHOR_Z": "0",
                "DRIFT_SCENE_WORLD": "world",
            },
            clear=False,
        ):
            selected_anchor, anchor_position, _, _, final_anchor = story_api._scene_anchor_position_for_inject(
                text="创建剧情 大风吹 在森林里",
                requested_anchor="home",
                player_id="vivn",
            )

        self.assertEqual(selected_anchor, "home")
        self.assertEqual(final_anchor, "home_safe_ground")
        self.assertEqual(anchor_position.get("world"), "world")
        self.assertEqual(anchor_position.get("x"), 12.0)
        self.assertEqual(anchor_position.get("y"), 65.0)
        self.assertEqual(anchor_position.get("z"), -8.0)

    def test_scene_anchor_skips_unsafe_water_like_blocks(self):
        recent_rows = [
            {
                "timestamp": 1700000200,
                "raw_payload": {
                    "event_type": "interact_block",
                    "payload": {
                        "block_type": "kelp_plant",
                        "location": {"world": "world", "x": 30.0, "y": 41.0, "z": 15.0},
                    },
                },
            }
        ]

        with patch("app.api.story_api._collect_rule_event_rows", return_value=recent_rows), patch.dict(
            "os.environ",
            {
                "DRIFT_ENABLE_SAFE_GROUND_ANCHOR": "true",
                "DRIFT_FIXED_ANCHOR_X": "0",
                "DRIFT_FIXED_ANCHOR_Y": "64",
                "DRIFT_FIXED_ANCHOR_Z": "0",
                "DRIFT_SCENE_WORLD": "world",
            },
            clear=False,
        ):
            selected_anchor, anchor_position, _, _, final_anchor = story_api._scene_anchor_position_for_inject(
                text="创建剧情 大风吹 在森林里",
                requested_anchor="home",
                player_id="vivn",
            )

        self.assertEqual(selected_anchor, "home")
        self.assertEqual(final_anchor, "home")
        self.assertEqual(anchor_position.get("world"), "world")
        self.assertEqual(anchor_position.get("x"), 0.0)
        self.assertEqual(anchor_position.get("y"), 64.0)
        self.assertEqual(anchor_position.get("z"), 0.0)

    def test_scene_anchor_zone_offset_uses_safe_ground_home_origin(self):
        recent_rows = [
            {
                "timestamp": 1700000300,
                "raw_payload": {
                    "event_type": "interact_block",
                    "payload": {
                        "block_type": "stone",
                        "location": {"world": "world", "x": 2.0, "y": 70.0, "z": 3.0},
                    },
                },
            }
        ]

        with patch("app.api.story_api._collect_rule_event_rows", return_value=recent_rows), patch.dict(
            "os.environ",
            {
                "DRIFT_ENABLE_SAFE_GROUND_ANCHOR": "true",
                "DRIFT_FIXED_ANCHOR_X": "0",
                "DRIFT_FIXED_ANCHOR_Y": "64",
                "DRIFT_FIXED_ANCHOR_Z": "0",
                "DRIFT_SCENE_WORLD": "world",
            },
            clear=False,
        ):
            selected_anchor, anchor_position, _, _, final_anchor = story_api._scene_anchor_position_for_inject(
                text="创建剧情 大风吹 在森林里",
                requested_anchor="npc_zone",
                player_id="vivn",
            )

        self.assertEqual(selected_anchor, "npc_zone")
        self.assertEqual(final_anchor, "npc_zone_safe_ground")
        self.assertEqual(anchor_position.get("world"), "world")
        self.assertEqual(anchor_position.get("x"), 26.0)
        self.assertEqual(anchor_position.get("y"), 71.0)
        self.assertEqual(anchor_position.get("z"), 3.0)

    def test_build_scene_events_generates_phase7_event_plan(self):
        snapshot = {
            "recent_rule_events": [
                {
                    "raw_payload": {"event_type": "collect", "payload": {"item_type": "wood", "count": 1}},
                    "event": {"event_type": "collect"},
                },
                {
                    "raw_payload": {"event_type": "collect", "payload": {"item_type": "torch", "count": 1}},
                    "event": {"event_type": "collect"},
                },
                {
                    "raw_payload": {"event_type": "collect", "payload": {"item_type": "pork", "count": 1}},
                    "event": {"event_type": "collect"},
                },
            ]
        }

        with patch("app.core.quest.runtime.quest_runtime.get_inventory_resources", return_value={}), patch(
            "app.core.quest.runtime.quest_runtime.get_debug_snapshot",
            return_value=snapshot,
        ), patch(
            "app.core.quest.runtime.quest_runtime._players",
            {},
        ):
            result = story_api.build_scene_events(
                player_id="vivn",
                scene_theme="大风吹",
                scene_hint=None,
                text="营地诗歌",
                anchor="home",
            )

        fragments = result["scene_plan"]["fragments"]
        self.assertEqual(fragments[:3], ["camp", "fire", "cooking_area"])
        self.assertIn("watchtower", fragments)

        event_ids = [event["event_id"] for event in result["event_plan"]]
        self.assertEqual(event_ids[:3], ["spawn_camp", "spawn_fire", "spawn_cooking_area"])
        self.assertIn("spawn_watchtower", event_ids)

    def test_scene_anchor_defaults_to_player_and_uses_player_position(self):
        with patch("app.api.story_api._collect_rule_event_rows", return_value=[]), patch.dict(
            "os.environ",
            {
                "DRIFT_ENABLE_SAFE_GROUND_ANCHOR": "false",
                "DRIFT_FIXED_ANCHOR_X": "0",
                "DRIFT_FIXED_ANCHOR_Y": "64",
                "DRIFT_FIXED_ANCHOR_Z": "0",
                "DRIFT_SCENE_WORLD": "world",
            },
            clear=False,
        ):
            selected_anchor, anchor_position, player_position, initial_anchor_position, final_anchor = story_api._scene_anchor_position_for_inject(
                text="创建剧情 营地",
                requested_anchor=None,
                player_id="vivn",
                player_position={"world": "world", "x": 123.4, "y": 66.6, "z": -8.2},
            )

        self.assertEqual(selected_anchor, "player")
        self.assertEqual(final_anchor, "player")
        self.assertEqual(anchor_position, {"world": "world", "x": 123.0, "y": 67.0, "z": -8.0})
        self.assertEqual(player_position, {"world": "world", "x": 123.0, "y": 67.0, "z": -8.0})
        self.assertEqual(initial_anchor_position, {"world": "world", "x": 123.0, "y": 67.0, "z": -8.0})

    def test_player_anchor_keeps_player_position_when_safe_ground_far_away(self):
        recent_rows = [
            {
                "timestamp": 1700001000,
                "raw_payload": {
                    "event_type": "interact_block",
                    "payload": {
                        "block_type": "grass_block",
                        "location": {"world": "world", "x": 0.0, "y": 64.0, "z": 0.0},
                    },
                },
            }
        ]

        with patch("app.api.story_api._collect_rule_event_rows", return_value=recent_rows), patch.dict(
            "os.environ",
            {
                "DRIFT_ENABLE_SAFE_GROUND_ANCHOR": "true",
                "DRIFT_SAFE_GROUND_PLAYER_RADIUS": "10",
                "DRIFT_FIXED_ANCHOR_X": "0",
                "DRIFT_FIXED_ANCHOR_Y": "64",
                "DRIFT_FIXED_ANCHOR_Z": "0",
                "DRIFT_SCENE_WORLD": "world",
            },
            clear=False,
        ):
            selected_anchor, anchor_position, player_position, initial_anchor_position, final_anchor = story_api._scene_anchor_position_for_inject(
                text="创建剧情 森林营地",
                requested_anchor="player",
                player_id="vivn",
                player_position={"world": "world", "x": -166.2, "y": 71.0, "z": -185.3},
            )

        self.assertEqual(selected_anchor, "player")
        self.assertEqual(final_anchor, "player")
        self.assertEqual(player_position, {"world": "world", "x": -166.0, "y": 71.0, "z": -185.0})
        self.assertEqual(initial_anchor_position, {"world": "world", "x": -166.0, "y": 71.0, "z": -185.0})
        self.assertEqual(anchor_position, {"world": "world", "x": -166.0, "y": 71.0, "z": -185.0})

    def test_player_anchor_prefers_nearby_safe_ground(self):
        recent_rows = [
            {
                "timestamp": 1700000900,
                "raw_payload": {
                    "event_type": "interact_block",
                    "payload": {
                        "block_type": "grass_block",
                        "location": {"world": "world", "x": 0.0, "y": 64.0, "z": 0.0},
                    },
                },
            },
            {
                "timestamp": 1700001100,
                "raw_payload": {
                    "event_type": "interact_block",
                    "payload": {
                        "block_type": "stone",
                        "location": {"world": "world", "x": -160.0, "y": 70.0, "z": -182.0},
                    },
                },
            },
        ]

        with patch("app.api.story_api._collect_rule_event_rows", return_value=recent_rows), patch.dict(
            "os.environ",
            {
                "DRIFT_ENABLE_SAFE_GROUND_ANCHOR": "true",
                "DRIFT_SAFE_GROUND_PLAYER_RADIUS": "10",
                "DRIFT_FIXED_ANCHOR_X": "0",
                "DRIFT_FIXED_ANCHOR_Y": "64",
                "DRIFT_FIXED_ANCHOR_Z": "0",
                "DRIFT_SCENE_WORLD": "world",
            },
            clear=False,
        ):
            selected_anchor, anchor_position, player_position, initial_anchor_position, final_anchor = story_api._scene_anchor_position_for_inject(
                text="创建剧情 森林营地",
                requested_anchor="player",
                player_id="vivn",
                player_position={"world": "world", "x": -166.2, "y": 71.0, "z": -185.3},
            )

        self.assertEqual(selected_anchor, "player")
        self.assertEqual(final_anchor, "player_safe_ground")
        self.assertEqual(player_position, {"world": "world", "x": -166.0, "y": 71.0, "z": -185.0})
        self.assertEqual(initial_anchor_position, {"world": "world", "x": -166.0, "y": 71.0, "z": -185.0})
        self.assertEqual(anchor_position, {"world": "world", "x": -160.0, "y": 71.0, "z": -182.0})

    def test_build_scene_events_preserves_scene_hint(self):
        snapshot = {
            "recent_rule_events": [
                {
                    "raw_payload": {"event_type": "collect", "payload": {"item_type": "wood", "count": 1}},
                    "event": {"event_type": "collect"},
                }
            ]
        }

        with patch("app.core.quest.runtime.quest_runtime.get_inventory_resources", return_value={}), patch(
            "app.core.quest.runtime.quest_runtime.get_debug_snapshot",
            return_value=snapshot,
        ), patch(
            "app.core.quest.runtime.quest_runtime._players",
            {},
        ):
            result = story_api.build_scene_events(
                player_id="vivn",
                scene_theme="大风吹",
                scene_hint="森林",
                text="营地诗歌",
                anchor="home",
            )

        self.assertEqual(result.get("scene_hint"), "森林")
        self.assertTrue(result.get("event_plan"))
        self.assertEqual(
            ((result["event_plan"][0].get("data") or {}).get("scene_hint")),
            "森林",
        )

    def test_resolve_inject_transaction_plan_prefers_scene_events(self):
        fake_scene_output = {
            "scene_theme": "大风吹",
            "selected_anchor": "home",
            "scene_plan": {"fragments": ["camp"]},
            "inventory_state": {"player_id": "vivn", "resources": {"wood": 1}, "updated_at_ms": 1},
            "event_plan": [
                {
                    "event_id": "spawn_camp",
                    "type": "spawn_structure",
                    "text": "spawn_camp",
                }
            ],
        }

        with patch("app.api.story_api.build_scene_events", return_value=fake_scene_output):
            tx_plan = story_api._resolve_inject_transaction_plan(
                player_id="vivn",
                text="test",
                payload={"version": "plugin_payload_v2", "hash": {"final_commands": "abc"}},
                requested_anchor="home",
                scene_theme="大风吹",
                scene_hint="森林",
            )

        self.assertEqual(tx_plan["tx_events"], fake_scene_output["event_plan"])
        self.assertEqual(tx_plan["selected_anchor"], "home")

    def test_resolve_inject_transaction_plan_falls_back_when_scene_empty(self):
        empty_scene_output = {
            "scene_theme": "静夜",
            "selected_anchor": "home",
            "scene_plan": {"fragments": []},
            "inventory_state": {"player_id": "vivn", "resources": {}, "updated_at_ms": 1},
            "event_plan": [],
        }

        with patch("app.api.story_api.build_scene_events", return_value=empty_scene_output):
            tx_plan = story_api._resolve_inject_transaction_plan(
                player_id="vivn",
                text="test",
                payload={"version": "plugin_payload_v2", "hash": {"final_commands": "abc"}},
                requested_anchor="home",
                scene_theme="静夜",
                scene_hint="森林",
            )

        self.assertTrue(isinstance(tx_plan["tx_events"], list) and tx_plan["tx_events"])
        self.assertEqual(tx_plan["tx_events"][0].get("event_id"), "scene_generation")

    def test_scene_meta_payload_keeps_event_plan_for_debugscene(self):
        scene_output = {
            "scene_theme": "大风吹",
            "scene_hint": "森林",
            "selected_anchor": "home",
            "initial_anchor": "player",
            "final_anchor": "player_safe_ground",
            "player_position": {"world": "world", "x": 10.0, "y": 65.0, "z": -3.0},
            "initial_anchor_position": {"world": "world", "x": 10.0, "y": 65.0, "z": -3.0},
            "final_anchor_position": {"world": "world", "x": 12.0, "y": 66.0, "z": -1.0},
            "anchor_position": {"world": "world", "x": 12.0, "y": 66.0, "z": -1.0},
            "scene_plan": {"fragments": ["camp", "fire"]},
            "scene_graph": {
                "root": "camp",
                "nodes": ["camp", "fire"],
                "edges": [{"from": "camp", "to": "fire"}],
            },
            "layout": {
                "strategy": "radial_v1",
                "root": "camp",
                "positions": {
                    "camp": {"x": 0, "z": 0},
                    "fire": {"x": 4, "z": 0},
                },
            },
            "scoring_debug": {
                "selected_root": "camp",
                "candidate_scores": [
                    {"fragment": "camp", "score": 5.5, "reason": "wood + light"},
                    {"fragment": "forge", "score": 1.0, "reason": "stone"},
                ],
                "selected_children": ["fire"],
                "blocked": [
                    {"fragment": "village", "stage": "root", "reason": "missing_required: food"}
                ],
                "reasons": {"selected_root": "wood + light", "selection_stage": "root_candidates"},
                "semantic_scores": {"wood": 1, "light": 1},
            },
            "inventory_state": {"resources": {"wood": 1, "torch": 1}},
            "event_plan": [
                {
                    "event_id": "spawn_camp",
                    "type": "spawn_structure",
                    "text": "spawn_camp",
                    "data": {"scene_hint": "森林", "scene_variant": "forest"},
                }
            ],
        }

        meta = story_api._scene_meta_payload(scene_output)

        self.assertEqual(meta.get("scene_theme"), "大风吹")
        self.assertEqual(meta.get("scene_hint"), "森林")
        self.assertEqual(meta.get("event_count"), 1)
        self.assertTrue(isinstance(meta.get("event_plan"), list) and meta.get("event_plan"))
        self.assertEqual(meta["event_plan"][0].get("event_id"), "spawn_camp")
        self.assertEqual(meta.get("player_pos"), {"world": "world", "x": 10.0, "y": 65.0, "z": -3.0})
        self.assertEqual(meta.get("initial_anchor"), "player")
        self.assertEqual(meta.get("final_anchor"), "player_safe_ground")
        self.assertEqual(meta.get("initial_anchor_pos"), {"world": "world", "x": 10.0, "y": 65.0, "z": -3.0})
        self.assertEqual(meta.get("final_anchor_pos"), {"world": "world", "x": 12.0, "y": 66.0, "z": -1.0})
        self.assertEqual(meta.get("anchor_pos"), {"world": "world", "x": 12.0, "y": 66.0, "z": -1.0})
        self.assertEqual((meta.get("scene_graph") or {}).get("root"), "camp")
        self.assertEqual((meta.get("scene_graph") or {}).get("nodes"), ["camp", "fire"])
        self.assertEqual(((meta.get("layout") or {}).get("positions") or {}).get("fire"), {"x": 4, "z": 0})
        self.assertEqual(meta.get("selected_root"), "camp")
        self.assertTrue(isinstance(meta.get("candidate_scores"), list) and meta.get("candidate_scores"))
        self.assertEqual(meta.get("candidate_scores")[0].get("fragment"), "camp")
        self.assertEqual(meta.get("candidate_scores")[0].get("score"), 5.5)
        self.assertEqual(meta.get("selected_children"), ["fire"])
        self.assertTrue(isinstance(meta.get("blocked"), list) and meta.get("blocked"))
        self.assertEqual(meta.get("blocked")[0].get("fragment"), "village")
        self.assertEqual((meta.get("reasons") or {}).get("selected_root"), "wood + light")
        self.assertEqual((meta.get("semantic_scores") or {}).get("wood"), 1)

    def test_scene_event_plan_to_world_patch_translates_spawn_npc(self):
        scene_output = {
            "event_plan": [
                {
                    "event_id": "spawn_npc",
                    "type": "spawn_npc",
                    "anchor": {"ref": "camp_edge", "world": "world"},
                    "data": {"npc_template": "wanderer"},
                }
            ]
        }

        patch = story_api._scene_event_plan_to_world_patch(scene_output)

        self.assertIn("mc", patch)
        self.assertIn("spawn_multi", patch["mc"])
        self.assertEqual(len(patch["mc"]["spawn_multi"]), 1)
        spawn = patch["mc"]["spawn_multi"][0]
        self.assertEqual(spawn.get("type"), "villager")
        self.assertEqual(spawn.get("name"), "阿无")
        self.assertEqual(spawn.get("world"), "world")

    def test_scene_event_plan_to_world_patch_translates_structure_block_fire(self):
        scene_output = {
            "event_plan": [
                {
                    "event_id": "spawn_camp",
                    "type": "spawn_structure",
                    "anchor": {"ref": "camp_center", "world": "world"},
                    "data": {"template": "camp_small"},
                },
                {
                    "event_id": "spawn_fire",
                    "type": "spawn_block",
                    "anchor": {"ref": "camp_center", "world": "world"},
                    "data": {"block": "campfire"},
                },
                {
                    "event_id": "spawn_fire_fallback",
                    "type": "spawn_fire",
                    "anchor": {"ref": "camp_center", "world": "world"},
                    "data": {},
                },
            ]
        }

        patch = story_api._scene_event_plan_to_world_patch(scene_output)

        mc_patch = patch.get("mc") or {}
        self.assertTrue(isinstance(mc_patch.get("structure"), list) and mc_patch.get("structure"))
        self.assertEqual(mc_patch["structure"][0].get("template"), "camp_small")
        self.assertTrue(isinstance(mc_patch.get("blocks"), list) and len(mc_patch["blocks"]) == 2)
        self.assertEqual(mc_patch["blocks"][0].get("type"), "campfire")
        self.assertEqual(mc_patch["blocks"][1].get("type"), "campfire")

        build_multi = mc_patch.get("build_multi") or []
        self.assertGreaterEqual(len(build_multi), 3)
        materials = [str(item.get("material") or "") for item in build_multi if isinstance(item, dict)]
        self.assertIn("CAMPFIRE", materials)
        self.assertIn("OAK_PLANKS", materials)

    def test_project_legacy_world_patch_to_anchor_shifts_spawn_spawns_blocks(self):
        mc_patch = {
            "spawn": {"x": 0, "y": 70, "z": 0},
            "spawns": [
                {"type": "villager", "name": "阿无", "x": 2, "y": 70, "z": 2},
            ],
            "blocks": [
                {"type": "oak_planks", "x": 0, "y": 70, "z": 0},
                {"type": "campfire", "x": 1, "y": 70, "z": 1},
            ],
        }
        anchor_position = {"world": "world", "x": -166.0, "y": 71.0, "z": -185.0}

        with patch.dict(
            "os.environ",
            {
                "DRIFT_AI_WORLD_REFERENCE_X": "0",
                "DRIFT_AI_WORLD_REFERENCE_Y": "70",
                "DRIFT_AI_WORLD_REFERENCE_Z": "0",
                "DRIFT_AI_WORLD_SHIFT_LIMIT": "512",
                "DRIFT_SCENE_WORLD": "world",
            },
            clear=False,
        ):
            projected = story_api._project_legacy_world_patch_to_anchor(mc_patch, anchor_position)

        self.assertEqual((projected.get("spawn") or {}).get("x"), -166)
        self.assertEqual((projected.get("spawn") or {}).get("y"), 71)
        self.assertEqual((projected.get("spawn") or {}).get("z"), -185)

        first_spawn = (projected.get("spawns") or [{}])[0]
        self.assertEqual(first_spawn.get("x"), -164)
        self.assertEqual(first_spawn.get("y"), 71)
        self.assertEqual(first_spawn.get("z"), -183)
        self.assertEqual(first_spawn.get("world"), "world")

        first_block = (projected.get("blocks") or [{}])[0]
        second_block = (projected.get("blocks") or [{}, {}])[1]
        self.assertEqual(first_block.get("x"), -166)
        self.assertEqual(first_block.get("y"), 71)
        self.assertEqual(first_block.get("z"), -185)
        self.assertEqual(first_block.get("world"), "world")
        self.assertEqual(second_block.get("x"), -165)
        self.assertEqual(second_block.get("y"), 71)
        self.assertEqual(second_block.get("z"), -184)

    def test_merge_scene_world_patch_preserves_existing_mc_ops(self):
        base_payload = {
            "version": "plugin_payload_v2",
            "mc": {
                "time": "day",
                "spawn": {
                    "type": "cow",
                    "name": "奶牛",
                    "offset": {"dx": -1, "dy": 0, "dz": -1},
                },
            },
        }
        scene_patch = {
            "mc": {
                "spawn_multi": [
                    {
                        "type": "villager",
                        "name": "阿无",
                        "offset": {"dx": 2, "dy": 0, "dz": 1},
                    }
                ]
            }
        }

        merged = story_api._merge_scene_world_patch(base_payload, scene_patch)

        self.assertEqual(merged.get("version"), "plugin_payload_v2")
        self.assertEqual((merged.get("mc") or {}).get("time"), "day")
        self.assertEqual(((merged.get("mc") or {}).get("spawn") or {}).get("name"), "奶牛")
        merged_spawn_multi = (merged.get("mc") or {}).get("spawn_multi") or []
        self.assertEqual(len(merged_spawn_multi), 1)
        self.assertEqual(merged_spawn_multi[0].get("name"), "阿无")

    def test_merge_scene_world_patch_merges_structure_and_block_lists(self):
        base_payload = {
            "version": "plugin_payload_v2",
            "mc": {
                "build_multi": [
                    {
                        "shape": "line",
                        "size": 1,
                        "material": "TORCH",
                    }
                ],
                "blocks": [
                    {
                        "type": "torch",
                        "offset": {"dx": 0, "dy": 0, "dz": 0},
                    }
                ],
            },
        }
        scene_patch = {
            "mc": {
                "build_multi": [
                    {
                        "shape": "line",
                        "size": 1,
                        "material": "CAMPFIRE",
                    }
                ],
                "blocks": [
                    {
                        "type": "campfire",
                        "offset": {"dx": 1, "dy": 0, "dz": 1},
                    }
                ],
                "structure": [
                    {
                        "template": "camp_small",
                    }
                ],
            }
        }

        merged = story_api._merge_scene_world_patch(base_payload, scene_patch)
        mc = merged.get("mc") or {}

        self.assertEqual(len(mc.get("build_multi") or []), 2)
        self.assertEqual(len(mc.get("blocks") or []), 2)
        self.assertEqual(len(mc.get("structure") or []), 1)
        self.assertEqual((mc.get("blocks") or [])[1].get("type"), "campfire")


if __name__ == "__main__":
    unittest.main()