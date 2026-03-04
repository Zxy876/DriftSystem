from __future__ import annotations

import hashlib
import json
import sys
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.scene.scene_llm_v1 import generate_scene_spec_from_text_v1


class SceneLlmV1Test(unittest.TestCase):
    def test_phrase_extract_lake_night_calm(self):
        result = generate_scene_spec_from_text_v1("平静夜晚的湖边")

        self.assertEqual(result.get("status"), "VALID")
        spec = result.get("scene_spec") or {}
        self.assertEqual(spec.get("scene_type"), "lake")
        self.assertEqual(spec.get("time_of_day"), "night")
        self.assertEqual(spec.get("mood"), "calm")

    def test_hash_stable_5_runs(self):
        hashes = []
        for _ in range(5):
            result = generate_scene_spec_from_text_v1("平静夜晚的湖边")
            payload = json.dumps(result.get("scene_spec"), ensure_ascii=False, sort_keys=True)
            hashes.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())

        self.assertTrue(all(h == hashes[0] for h in hashes))

    def test_llm_alias_values_are_normalized(self):
        with mock.patch(
            "app.core.scene.scene_llm_v1._llm_extract",
            return_value=(
                True,
                {
                    "scene_type": "湖边",
                    "time_of_day": "夜晚",
                    "weather": "晴朗",
                    "mood": "平静",
                },
            ),
        ):
            result = generate_scene_spec_from_text_v1("湖边夜晚木屋")

        self.assertEqual(result.get("status"), "VALID")
        spec = result.get("scene_spec") or {}
        self.assertEqual(spec.get("scene_type"), "lake")
        self.assertEqual(spec.get("time_of_day"), "night")
        self.assertEqual(spec.get("weather"), "clear")
        self.assertEqual(spec.get("mood"), "calm")

    def test_unknown_llm_scene_type_does_not_override_rule_extract(self):
        with mock.patch(
            "app.core.scene.scene_llm_v1._llm_extract",
            return_value=(
                True,
                {
                    "scene_type": "city",
                    "time_of_day": "night",
                    "weather": "rain",
                    "mood": "tense",
                },
            ),
        ):
            result = generate_scene_spec_from_text_v1("平静夜晚的湖边")

        self.assertEqual(result.get("status"), "VALID")
        spec = result.get("scene_spec") or {}
        self.assertEqual(spec.get("scene_type"), "lake")
        self.assertEqual(spec.get("time_of_day"), "night")
        self.assertEqual(spec.get("weather"), "rain")
        self.assertEqual(spec.get("mood"), "tense")


if __name__ == "__main__":
    unittest.main()
