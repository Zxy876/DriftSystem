from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.generation.spec_validator import validate_spec


def _valid_spec() -> dict:
    return {
        "structure_type": "house",
        "width": 7,
        "depth": 5,
        "height": 4,
        "material_preference": "wood",
        "roof_type": "flat",
        "orientation": "south",
        "features": {
            "door": {"enabled": True, "side": "front"},
            "windows": {"enabled": True, "count": 2},
        },
    }


class SpecValidatorTest(unittest.TestCase):
    def test_valid_spec(self):
        result = validate_spec(_valid_spec())
        self.assertEqual(result.get("status"), "VALID")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertIsInstance(result.get("spec"), dict)
        self.assertEqual(result["spec"]["width"], 7)

    def test_missing_field(self):
        payload = _valid_spec()
        payload.pop("height")

        result = validate_spec(payload)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "MISSING_FIELD")
        self.assertIsNone(result.get("spec"))

    def test_invalid_enum(self):
        payload = _valid_spec()
        payload["structure_type"] = "castle"

        result = validate_spec(payload)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "INVALID_ENUM")

    def test_out_of_range(self):
        payload = _valid_spec()
        payload["width"] = 2

        result = validate_spec(payload)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "OUT_OF_RANGE")

    def test_forbidden_exec_field(self):
        payload = _valid_spec()
        payload["blocks"] = [{"x": 0, "y": 0, "z": 0, "block": "oak_planks"}]

        result = validate_spec(payload)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "FORBIDDEN_EXEC_FIELD")

    def test_unknown_field(self):
        payload = _valid_spec()
        payload["window_style"] = "arch"

        result = validate_spec(payload)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "UNKNOWN_FIELD")

    def test_invalid_nested_windows_count(self):
        payload = _valid_spec()
        payload["features"]["windows"]["count"] = 5

        result = validate_spec(payload)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "INVALID_FEATURE_CONFIG")

    def test_invalid_door_side(self):
        payload = _valid_spec()
        payload["features"]["door"]["side"] = "left"

        result = validate_spec(payload)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "INVALID_FEATURE_CONFIG")

    def test_invalid_nested_type(self):
        payload = _valid_spec()
        payload["features"] = "door:true"

        result = validate_spec(payload)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "INVALID_NESTED_FIELD")


if __name__ == "__main__":
    unittest.main()
