from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.runtime.interaction_event import create_interaction_event
from app.core.runtime.resource_mapping import (
    RESOURCE_BINDING_VERSION,
    RESOURCE_INVENTORY_VERSION,
    bind_resources_to_scene,
    create_resource_inventory,
    detect_missing_resources,
    resource_binding_hash,
)
from app.core.runtime.state_reducer import reduce_event_log, replay_event_log_to_patch


class Phase4ResourceMappingModuleBTest(unittest.TestCase):
    def test_b1_resource_inventory_versioned_structure(self):
        inventory = create_resource_inventory(
            player_id="player_b",
            resources=["Wood", "paper", "wood", " Lantern "],
            timestamp_ms=1700000000000,
        )

        self.assertEqual(inventory.version, RESOURCE_INVENTORY_VERSION)
        self.assertEqual(inventory.player_id, "player_b")
        self.assertEqual(inventory.resources, ["lantern", "paper", "wood", "wood"])
        self.assertEqual(inventory.timestamp_ms, 1700000000000)

    def test_b2_missing_resources_detection_and_degrade(self):
        inventory = create_resource_inventory(
            player_id="player_b",
            resources=["wood"],
            timestamp_ms=1,
        )

        missing = detect_missing_resources(
            scene_requirements=["paper", "lantern", "wood"],
            inventory=inventory,
        )
        self.assertEqual(missing, ["lantern", "paper"])

        binding = bind_resources_to_scene(
            scene_requirements=["paper", "lantern", "wood"],
            inventory=inventory,
        )
        self.assertEqual(binding["version"], RESOURCE_BINDING_VERSION)
        self.assertEqual(binding["binding_status"], "DEGRADED")
        self.assertEqual(binding["degrade_patch_type"], "text_patch")
        self.assertEqual(binding["missing_resources"], ["lantern", "paper"])

    def test_b3_deterministic_resource_binding_hash(self):
        inventory_a = create_resource_inventory(
            player_id="player_b",
            resources=["paper", "wood", "lantern"],
            timestamp_ms=10,
        )
        inventory_b = create_resource_inventory(
            player_id="player_b",
            resources=["lantern", "paper", "wood"],
            timestamp_ms=999,
        )

        hash_a = resource_binding_hash(
            scene_requirements=["wood", "paper"],
            inventory=inventory_a,
        )
        hash_b = resource_binding_hash(
            scene_requirements=["paper", "wood"],
            inventory=inventory_b,
        )

        self.assertEqual(hash_a, hash_b)

        inventory_c = create_resource_inventory(
            player_id="player_b",
            resources=["paper", "wood"],
            timestamp_ms=10,
        )
        hash_c = resource_binding_hash(
            scene_requirements=["wood", "paper", "lantern"],
            inventory=inventory_c,
        )
        self.assertNotEqual(hash_a, hash_c)

    def test_reducer_populates_inventory_and_patch_payload(self):
        events = [
            create_interaction_event(
                event_type="collect",
                event_id="evt_collect_1",
                player_id="player_b",
                timestamp_ms=100,
                data={"resource": "paper", "amount": 2},
            ),
            create_interaction_event(
                event_type="collect",
                event_id="evt_collect_2",
                player_id="player_b",
                timestamp_ms=101,
                data={"resource": "lantern", "amount": 1},
            ),
        ]

        state = reduce_event_log(events)
        self.assertIn("inventory", state)
        self.assertEqual(state["inventory"]["version"], RESOURCE_INVENTORY_VERSION)
        self.assertEqual(state["inventory"]["player_id"], "player_b")
        self.assertEqual(state["inventory"]["resources"], ["lantern", "paper", "paper"])

        replay = replay_event_log_to_patch(events)
        inventory_resources = replay["world_patch"]["payload"]["inventory_resources"]
        self.assertEqual(inventory_resources, ["lantern", "paper", "paper"])


if __name__ == "__main__":
    unittest.main()
