from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.executor.executor_v1 import execute_payload_v1
from app.core.executor.plugin_payload_v1 import build_plugin_payload_v1
from app.core.executor.plugin_payload_v2 import build_plugin_payload_v2
from app.core.executor.replay_v1 import replay_payload_v1


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


class Gate5CompatibilityRejectionTest(unittest.TestCase):
    def test_v2_payload_rejected_by_executor_v1(self):
        payload_v2 = build_plugin_payload_v2(_compose_fixture(with_npc=True), player_id="gate5", strict_mode=False)

        result = execute_payload_v1(payload_v2)
        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "UNSUPPORTED_PAYLOAD_VERSION")

    def test_v2_payload_rejected_by_replay_v1(self):
        payload_v2 = build_plugin_payload_v2(_compose_fixture(with_npc=True), player_id="gate5", strict_mode=False)

        result = replay_payload_v1(payload_v2)
        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "UNSUPPORTED_REPLAY_VERSION")

    def test_v1_payload_executes_in_executor_v1(self):
        payload_v1 = build_plugin_payload_v1(_compose_fixture(with_npc=False), player_id="gate5")

        result = execute_payload_v1(payload_v1)
        self.assertEqual(result.get("status"), "SUCCESS")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertGreater(int(result.get("executed_commands") or 0), 0)
        self.assertIsInstance(result.get("world_state_hash"), str)


if __name__ == "__main__":
    unittest.main()
