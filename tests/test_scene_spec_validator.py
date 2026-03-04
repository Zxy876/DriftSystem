from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.scene.scene_spec_validator import validate_scene_spec


def _valid_scene_spec() -> dict:
    return {
        "scene_type": "lake",
        "time_of_day": "night",
        "weather": "clear",
        "mood": "calm",
    }


class SceneSpecValidatorTest(unittest.TestCase):
    def test_valid_scene_spec(self):
        result = validate_scene_spec(_valid_scene_spec())
        self.assertEqual(result.get("status"), "VALID")
        self.assertEqual(result.get("failure_code"), "NONE")

    def test_missing_field(self):
        payload = _valid_scene_spec()
        payload.pop("mood")
        result = validate_scene_spec(payload)
        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "MISSING_FIELD")

    def test_invalid_scene_type(self):
        payload = _valid_scene_spec()
        payload["scene_type"] = "city"
        result = validate_scene_spec(payload)
        self.assertEqual(result.get("failure_code"), "INVALID_SCENE_TYPE")

    def test_invalid_time(self):
        payload = _valid_scene_spec()
        payload["time_of_day"] = "dusk"
        result = validate_scene_spec(payload)
        self.assertEqual(result.get("failure_code"), "INVALID_TIME")

    def test_invalid_weather(self):
        payload = _valid_scene_spec()
        payload["weather"] = "snow"
        result = validate_scene_spec(payload)
        self.assertEqual(result.get("failure_code"), "INVALID_WEATHER")

    def test_invalid_mood(self):
        payload = _valid_scene_spec()
        payload["mood"] = "happy"
        result = validate_scene_spec(payload)
        self.assertEqual(result.get("failure_code"), "INVALID_MOOD")

    def test_blocks_forbidden(self):
        payload = _valid_scene_spec()
        payload["blocks"] = []
        result = validate_scene_spec(payload)
        self.assertEqual(result.get("failure_code"), "MISSING_FIELD")


if __name__ == "__main__":
    unittest.main()
