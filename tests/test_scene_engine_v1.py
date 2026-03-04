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

from app.core.scene.scene_engine_v1 import generate_scene_patch


class SceneEngineV1Test(unittest.TestCase):
    def test_lake_is_deterministic_5_runs(self):
        spec = {
            "scene_type": "lake",
            "time_of_day": "day",
            "weather": "clear",
            "mood": "calm",
        }

        runs = [generate_scene_patch(spec) for _ in range(5)]
        counts = [len(r.get("blocks") or []) for r in runs]
        hashes = []
        for r in runs:
            payload = json.dumps(r.get("blocks"), ensure_ascii=False, sort_keys=True)
            hashes.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())

        self.assertTrue(all(r.get("build_status") == "SUCCESS" for r in runs))
        self.assertEqual(counts[0], 198)
        self.assertTrue(all(c == counts[0] for c in counts))
        self.assertTrue(all(h == hashes[0] for h in hashes))

    def test_different_scene_types_have_different_hashes(self):
        lake = generate_scene_patch({
            "scene_type": "lake",
            "time_of_day": "day",
            "weather": "clear",
            "mood": "calm",
        })
        forest = generate_scene_patch({
            "scene_type": "forest",
            "time_of_day": "day",
            "weather": "clear",
            "mood": "mysterious",
        })

        lake_hash = hashlib.sha256(
            json.dumps(lake.get("blocks"), ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        forest_hash = hashlib.sha256(
            json.dumps(forest.get("blocks"), ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        self.assertNotEqual(lake_hash, forest_hash)

    def test_village_block_count_fixed(self):
        village = generate_scene_patch({
            "scene_type": "village",
            "time_of_day": "day",
            "weather": "clear",
            "mood": "calm",
        })
        self.assertEqual(village.get("build_status"), "SUCCESS")
        self.assertEqual(len(village.get("blocks") or []), 261)


if __name__ == "__main__":
    unittest.main()
