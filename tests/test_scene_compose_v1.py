from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.scene.scene_orchestrator_v1 import compose_scene_and_structure


class SceneComposeV1Test(unittest.TestCase):
    def test_compose_lake_house_is_success_and_deterministic(self):
        prompt = "平静夜晚的湖边，建一个7x5木屋"

        runs = [compose_scene_and_structure(prompt) for _ in range(5)]

        self.assertTrue(all(r.get("status") == "SUCCESS" for r in runs))

        hashes = [r.get("merge_hash") for r in runs]
        self.assertTrue(all(h == hashes[0] for h in hashes))

        for result in runs:
            scene_count = result.get("scene_block_count")
            spec_count = result.get("spec_block_count")
            merged_count = result.get("merged_block_count")

            self.assertGreaterEqual(merged_count, max(scene_count, spec_count))
            self.assertLessEqual(merged_count, scene_count + spec_count)


if __name__ == "__main__":
    unittest.main()
