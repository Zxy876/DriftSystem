from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.executor.canonical_v2 import stable_hash_v2
from app.core.runtime.interaction_event import create_interaction_event
from app.core.runtime.state_reducer import reduce_event_log, replay_event_log_to_patch, runtime_state_hash
from app.core.runtime.world_patch import WORLD_PATCH_HOME_ANCHOR, WORLD_PATCH_VERSION, generate_world_patch, resolve_world_patch_anchor


class Phase4WorldPatchModuleDTest(unittest.TestCase):
    def test_d1_anchor_resolution_order_player_scene_npc_home(self):
        runtime_state = {
            "scene_anchor": {"base_x": 20, "base_y": 70, "base_z": 20, "anchor_mode": "scene"},
            "npc_state": {
                "npc_guard": {
                    "npc_id": "npc_guard",
                    "npc_available": True,
                    "anchor": {"base_x": 30, "base_y": 70, "base_z": 30, "anchor_mode": "fixed"},
                }
            },
        }

        player_event = create_interaction_event(
            event_type="talk",
            event_id="evt_anchor_player",
            player_id="p1",
            npc_id="npc_guard",
            timestamp_ms=100,
            data={
                "player_anchor": {"base_x": 10, "base_y": 70, "base_z": 10, "anchor_mode": "player"},
                "scene_anchor": {"base_x": 21, "base_y": 70, "base_z": 21, "anchor_mode": "scene"},
            },
        )
        resolved_player = resolve_world_patch_anchor(source_event=player_event, runtime_state=runtime_state)
        self.assertEqual(resolved_player["source"], "player")
        self.assertEqual(resolved_player["anchor"]["base_x"], 10)

        scene_event = create_interaction_event(
            event_type="talk",
            event_id="evt_anchor_scene",
            player_id="p1",
            npc_id="npc_guard",
            timestamp_ms=101,
            data={"scene_anchor": {"base_x": 21, "base_y": 70, "base_z": 21, "anchor_mode": "scene"}},
        )
        resolved_scene = resolve_world_patch_anchor(source_event=scene_event, runtime_state=runtime_state)
        self.assertEqual(resolved_scene["source"], "scene")
        self.assertEqual(resolved_scene["anchor"]["base_x"], 21)

        npc_event = create_interaction_event(
            event_type="talk",
            event_id="evt_anchor_npc",
            player_id="p1",
            npc_id="npc_guard",
            timestamp_ms=102,
        )
        resolved_npc = resolve_world_patch_anchor(source_event=npc_event, runtime_state={"npc_state": runtime_state["npc_state"]})
        self.assertEqual(resolved_npc["source"], "npc")
        self.assertEqual(resolved_npc["anchor"]["base_x"], 30)

        home_event = create_interaction_event(
            event_type="collect",
            event_id="evt_anchor_home",
            player_id="p1",
            timestamp_ms=103,
            data={"resource": "wood", "amount": 1},
        )
        resolved_home = resolve_world_patch_anchor(source_event=home_event, runtime_state={})
        self.assertEqual(resolved_home["source"], "home")
        self.assertEqual(resolved_home["anchor"], WORLD_PATCH_HOME_ANCHOR)

    def test_d2_world_patch_generator_required_fields(self):
        events = [
            create_interaction_event(
                event_type="talk",
                event_id="evt_d2_talk",
                player_id="p1",
                npc_id="npc_guard",
                timestamp_ms=200,
                data={"relationship_delta": 0.4, "threshold": 0.6},
            ),
            create_interaction_event(
                event_type="collect",
                event_id="evt_d2_collect",
                player_id="p1",
                timestamp_ms=201,
                data={"resource": "paper", "amount": 2},
            ),
        ]
        state = reduce_event_log(events)
        state_hash = runtime_state_hash(state)

        patch = generate_world_patch(
            source_event=events[-1],
            runtime_state=state,
            input_state_hash=state_hash,
        )

        self.assertEqual(patch["version"], WORLD_PATCH_VERSION)
        self.assertEqual(patch["source_event"], "evt_d2_collect")
        self.assertEqual(patch["input_state_hash"], state_hash)
        self.assertEqual(patch["payload_hash"], stable_hash_v2(patch["payload"]))
        self.assertEqual(patch["patch_id"], f"patch_{patch['payload_hash'][:12]}")

        required_keys = {
            "version",
            "patch_id",
            "source_event",
            "input_state_hash",
            "payload_hash",
            "anchor",
            "timestamp",
            "payload",
        }
        self.assertTrue(required_keys.issubset(set(patch.keys())))

    def test_d3_event_replay_patch_is_deterministic(self):
        events = [
            create_interaction_event(
                event_type="talk",
                event_id="evt_d3_talk",
                player_id="p1",
                npc_id="npc_guard",
                timestamp_ms=300,
                data={"relationship_delta": 0.5, "threshold": 0.6},
            ),
            create_interaction_event(
                event_type="trigger",
                event_id="evt_d3_trigger",
                player_id="p1",
                timestamp_ms=301,
                data={"trigger": "memory.mother"},
            ),
        ]

        first = replay_event_log_to_patch(events)
        second = replay_event_log_to_patch(events)

        self.assertEqual(first["state_hash"], second["state_hash"])
        self.assertEqual(first["payload_hash"], second["payload_hash"])
        self.assertEqual(first["world_patch"], second["world_patch"])
        self.assertEqual(first["world_patch"]["input_state_hash"], first["state_hash"])
        self.assertEqual(first["world_patch"]["payload_hash"], first["payload_hash"])


if __name__ == "__main__":
    unittest.main()
