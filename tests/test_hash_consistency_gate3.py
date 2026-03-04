from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.executor.canonical_v2 import final_commands_hash_v2
from app.core.executor.plugin_payload_v1 import build_plugin_payload_v1
from app.core.executor.plugin_payload_v2 import build_plugin_payload_v2


def _compose_fixture(*, with_npc: bool) -> dict:
    blocks = [
        {"x": 0, "y": 64, "z": 0, "block": "grass_block"},
        {"x": 1, "y": 64, "z": 0, "block": "oak_planks"},
    ]
    if with_npc:
        blocks.append({"x": 2, "y": 64, "z": 0, "block": "npc_placeholder"})

    return {
        "status": "SUCCESS",
        "failure_code": "NONE",
        "scene_spec": {"scene_type": "lake", "time_of_day": "night", "weather": "clear", "mood": "calm"},
        "scene_patch": {"build_status": "SUCCESS", "failure_code": "NONE", "blocks": []},
        "structure_patch": {"build_status": "SUCCESS", "failure_code": "NONE", "blocks": blocks},
        "merged": {
            "status": "SUCCESS",
            "failure_code": "NONE",
            "blocks": blocks,
            "conflicts_total": 0,
            "spec_dropped_total": 0,
        },
        "validation": {"status": "VALID", "failure_code": "NONE"},
        "scene_block_count": 0,
        "spec_block_count": len(blocks),
        "merged_block_count": len(blocks),
        "merge_hash": "",
        "mapping_result": {
            "trace": {
                "rule_version": "rule_v2_2",
            }
        },
    }


class HashConsistencyGate3Test(unittest.TestCase):
    def test_v1_hash_field_is_merged_blocks_only(self):
        payload = build_plugin_payload_v1(_compose_fixture(with_npc=False), player_id="tester")
        self.assertEqual(payload.get("version"), "plugin_payload_v1")
        self.assertIn("merged_blocks", payload.get("hash") or {})
        self.assertNotIn("final_commands", payload.get("hash") or {})

    def test_v2_hash_field_is_final_commands(self):
        payload = build_plugin_payload_v2(_compose_fixture(with_npc=True), player_id="tester", strict_mode=False)
        self.assertEqual(payload.get("version"), "plugin_payload_v2")
        self.assertIn("final_commands", payload.get("hash") or {})
        self.assertEqual((payload.get("hash") or {}).get("final_commands"), payload.get("final_commands_hash_v2"))

    def test_cross_version_hash_not_confused(self):
        base = _compose_fixture(with_npc=True)
        v1 = build_plugin_payload_v1(base, player_id="tester")
        v2 = build_plugin_payload_v2(base, player_id="tester", strict_mode=False)
        self.assertNotEqual((v1.get("hash") or {}).get("merged_blocks"), (v2.get("hash") or {}).get("final_commands"))

    def test_v2_hash_is_permutation_invariant(self):
        block_ops = [
            {"x": 4, "y": 64, "z": 4, "block": "stone"},
            {"x": 1, "y": 64, "z": 1, "block": "oak_planks"},
        ]
        entity_ops = [
            {
                "type": "summon",
                "entity_type": "villager",
                "x": 2,
                "y": 64,
                "z": 2,
                "name": "Lake Guard",
                "profession": "none",
                "no_ai": True,
                "silent": True,
                "rotation": 90,
            }
        ]

        hash_a = final_commands_hash_v2(block_ops, entity_ops)
        hash_b = final_commands_hash_v2(list(reversed(block_ops)), list(reversed(entity_ops)))
        self.assertEqual(hash_a, hash_b)


if __name__ == "__main__":
    unittest.main()
