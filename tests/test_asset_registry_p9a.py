from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.assets.asset_loader import asset_registry_info, get_asset_registry, reset_asset_registry_cache


class AssetRegistryP9ATest(unittest.TestCase):
    def setUp(self) -> None:
        reset_asset_registry_cache()

    def test_registry_loads_v1_and_assets(self):
        registry = get_asset_registry()
        self.assertEqual(registry.version, "1.0")

        asset_ids = registry.list_assets()
        self.assertTrue(asset_ids)
        self.assertIn("camp", asset_ids)

    def test_filter_by_semantics_matches_expected_asset(self):
        registry = get_asset_registry()
        selected = registry.filter_by_semantics(["wood", "fire"])
        self.assertIn("camp", selected)

    def test_registry_info_returns_version_and_count(self):
        info = asset_registry_info()
        self.assertEqual(info.get("version"), "1.0")
        self.assertGreaterEqual(int(info.get("asset_count") or 0), 1)


if __name__ == "__main__":
    unittest.main()
