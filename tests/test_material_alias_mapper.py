from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.generation.deterministic_build_engine import build_from_spec
from app.core.generation.material_alias_mapper import BLOCK_ID_WHITELIST, map_roles_to_blocks


def _house_spec() -> dict:
    return {
        "structure_type": "house",
        "width": 7,
        "depth": 5,
        "height": 4,
        "material_preference": "wood",
        "roof_type": "flat",
    }


class MaterialAliasMapperTest(unittest.TestCase):
    def test_wood_house_maps_to_whitelist_blocks(self):
        role_blocks = build_from_spec(_house_spec())["blocks"]

        result = map_roles_to_blocks(role_blocks, "wood")

        self.assertEqual(result.get("status"), "SUCCESS")
        self.assertEqual(result.get("failure_code"), "NONE")
        blocks = result.get("blocks")
        self.assertTrue(blocks)
        self.assertTrue(all(entry.get("block") in BLOCK_ID_WHITELIST for entry in blocks))

    def test_unknown_role_rejected(self):
        role_blocks = [{"x": 0, "y": 0, "z": 0, "role": "DOOR"}]

        result = map_roles_to_blocks(role_blocks, "wood")

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "UNKNOWN_ROLE")

    def test_invalid_material_preference_rejected(self):
        role_blocks = [{"x": 0, "y": 0, "z": 0, "role": "FLOOR"}]

        result = map_roles_to_blocks(role_blocks, "glass")

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "INVALID_MATERIAL_PREFERENCE")

    def test_empty_blocks_rejected(self):
        result = map_roles_to_blocks([], "wood")

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "EMPTY_BLOCKS")

    def test_window_and_door_air_roles_are_mapped(self):
        role_blocks = [
            {"x": 0, "y": 2, "z": 1, "role": "WINDOW"},
            {"x": 3, "y": 1, "z": 0, "role": "DOOR_AIR"},
        ]

        result = map_roles_to_blocks(role_blocks, "wood")

        self.assertEqual(result.get("status"), "SUCCESS")
        mapped = result.get("blocks") or []
        block_ids = {entry.get("block") for entry in mapped}
        self.assertIn("glass_pane", block_ids)
        self.assertIn("air", block_ids)


if __name__ == "__main__":
    unittest.main()
