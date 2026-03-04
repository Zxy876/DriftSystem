from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.generation.deterministic_build_engine import build_from_spec


def _house_spec() -> dict:
    return {
        "structure_type": "house",
        "width": 7,
        "depth": 5,
        "height": 4,
        "material_preference": "wood",
        "roof_type": "flat",
    }


class DeterministicBuildEngineTest(unittest.TestCase):
    def test_same_spec_is_identical_across_runs(self):
        spec = _house_spec()
        baseline = build_from_spec(spec)

        self.assertEqual(baseline.get("build_status"), "SUCCESS")
        self.assertEqual(baseline.get("failure_code"), "NONE")

        baseline_blocks = baseline.get("blocks")
        self.assertIsInstance(baseline_blocks, list)

        for _ in range(4):
            current = build_from_spec(spec)
            self.assertEqual(current, baseline)

    def test_house_7x5_block_count_is_fixed(self):
        result = build_from_spec(_house_spec())

        self.assertEqual(result.get("build_status"), "SUCCESS")
        self.assertEqual(result.get("failure_code"), "NONE")

        blocks = result.get("blocks")
        self.assertIsInstance(blocks, list)
        self.assertEqual(len(blocks), 130)

        payload = json.dumps(blocks, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.assertEqual(len(digest), 64)

    def test_unsupported_structure_returns_rejected(self):
        spec = _house_spec()
        spec["structure_type"] = "castle"

        result = build_from_spec(spec)

        self.assertEqual(result.get("build_status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "UNSUPPORTED_STRUCTURE")
        self.assertEqual(result.get("blocks"), [])


if __name__ == "__main__":
    unittest.main()
