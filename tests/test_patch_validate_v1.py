from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.patch.patch_validate_v1 import validate_blocks


class PatchValidateV1Test(unittest.TestCase):
    def test_empty_blocks_rejected(self):
        result = validate_blocks([])

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "EMPTY_BLOCKS")

    def test_too_many_blocks_rejected(self):
        blocks = [{"x": i, "y": 64, "z": 0, "block": "oak_planks"} for i in range(3)]
        result = validate_blocks(blocks, max_blocks=2)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "TOO_MANY_BLOCKS")

    def test_non_int_coord_rejected(self):
        blocks = [{"x": "1", "y": 64, "z": 0, "block": "oak_planks"}]
        result = validate_blocks(blocks)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "INVALID_COORD")


if __name__ == "__main__":
    unittest.main()
