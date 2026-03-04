from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.patch.patch_merge_v1 import merge_blocks


class PatchMergeV1Test(unittest.TestCase):
    def test_scene_non_air_wins_on_conflict(self):
        scene_blocks = [{"x": 1, "y": 64, "z": 1, "block": "water"}]
        spec_blocks = [{"x": 1, "y": 64, "z": 1, "block": "oak_planks"}]

        result = merge_blocks(scene_blocks, spec_blocks)

        self.assertEqual(result.get("status"), "SUCCESS")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("conflicts_total"), 1)
        self.assertEqual(result.get("spec_dropped_total"), 1)
        self.assertEqual(result.get("blocks"), [{"x": 1, "y": 64, "z": 1, "block": "water"}])

    def test_scene_air_does_not_override_spec(self):
        scene_blocks = [{"x": 1, "y": 64, "z": 1, "block": "air"}]
        spec_blocks = [{"x": 1, "y": 64, "z": 1, "block": "oak_planks"}]

        result = merge_blocks(scene_blocks, spec_blocks)

        self.assertEqual(result.get("status"), "SUCCESS")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("conflicts_total"), 1)
        self.assertEqual(result.get("spec_dropped_total"), 0)
        self.assertEqual(result.get("blocks"), [{"x": 1, "y": 64, "z": 1, "block": "oak_planks"}])

    def test_order_and_hash_are_stable(self):
        scene_a = [
            {"x": 2, "y": 64, "z": 1, "block": "water"},
            {"x": 0, "y": 64, "z": 0, "block": "lantern"},
        ]
        spec_a = [
            {"x": 1, "y": 64, "z": 0, "block": "oak_planks"},
            {"x": 2, "y": 64, "z": 1, "block": "stone"},
        ]

        scene_b = list(reversed(scene_a))
        spec_b = list(reversed(spec_a))

        first = merge_blocks(scene_a, spec_a)
        second = merge_blocks(scene_b, spec_b)

        self.assertEqual(first.get("status"), "SUCCESS")
        self.assertEqual(second.get("status"), "SUCCESS")
        self.assertEqual(first.get("blocks"), second.get("blocks"))
        self.assertEqual(first.get("hash"), second.get("hash"))


if __name__ == "__main__":
    unittest.main()
