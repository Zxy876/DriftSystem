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

from app.core.generation.spec_engine_v1 import generate_patch_from_text_v1


class SpecEngineV1PipelineTest(unittest.TestCase):
    def test_pipeline_success_has_fixed_metadata(self):
        result = generate_patch_from_text_v1("给我建一个7x5的木屋")

        self.assertEqual(result.get("build_status"), "SUCCESS")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("build_path"), "spec_engine_v1")
        self.assertEqual(result.get("patch_source"), "deterministic_engine")

    def test_pipeline_house_count_and_hash_fixed(self):
        result = generate_patch_from_text_v1("给我建一个7x5的木屋")
        blocks = result.get("blocks")

        self.assertEqual(result.get("build_status"), "SUCCESS")
        self.assertIsInstance(blocks, list)
        self.assertEqual(len(blocks), 130)

        payload = json.dumps(blocks, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        self.assertEqual(
            digest,
            "58320b094e0c165877b73672ce74fcc8a55554884b179b6fd39d5c5b912c47c4",
        )

    def test_pipeline_with_door_and_windows_is_stable(self):
        prompt = "给我建一个7x5的木屋，门朝南，开两扇窗"
        runs = [generate_patch_from_text_v1(prompt) for _ in range(5)]

        for result in runs:
            self.assertEqual(result.get("build_status"), "SUCCESS")
            self.assertEqual(result.get("failure_code"), "NONE")

        block_counts = [len(r.get("blocks") or []) for r in runs]
        self.assertTrue(all(count == block_counts[0] for count in block_counts))

        hashes = []
        for result in runs:
            payload = json.dumps(result.get("blocks"), ensure_ascii=False, sort_keys=True)
            hashes.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())

        self.assertTrue(all(h == hashes[0] for h in hashes))


if __name__ == "__main__":
    unittest.main()
