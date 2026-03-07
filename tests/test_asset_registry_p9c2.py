from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.assets.asset_loader import asset_registry_info, get_asset_registry, reset_asset_registry_cache
from app.core.assets.asset_registry import AssetRegistry, AssetRegistryConflictError
from app.core.packs.pack_types import PackMeta


class _StaticPackRegistry:
    def __init__(self, packs):
        self._packs = list(packs)

    def enabled(self):
        return list(self._packs)


class AssetRegistryP9C2Test(unittest.TestCase):
    def setUp(self) -> None:
        reset_asset_registry_cache()

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _make_pack(
        self,
        base_dir: Path,
        *,
        pack_id: str,
        namespace: str,
        priority: int,
        assets: list[dict],
    ) -> PackMeta:
        pack_dir = base_dir / pack_id
        pack_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(pack_dir / "assets.json", {"assets": assets})
        return PackMeta(
            pack_id=pack_id,
            version="1.0",
            namespace=namespace,
            priority=priority,
            enabled=True,
            pack_path=str(pack_dir),
        )

    def test_default_registry_merges_enabled_pack_assets(self):
        registry = get_asset_registry()
        asset_ids = set(registry.list_assets())

        expected_pack_assets = {
            "vanilla:camp_watch",
            "ruins:ruins_arch",
            "ruins:ruined_gate",
            "poetry:lonely_fire",
            "poetry:falling_moon",
        }
        self.assertTrue(expected_pack_assets.issubset(asset_ids))

        info = asset_registry_info()
        self.assertGreaterEqual(int(info.get("pack_asset_count") or 0), len(expected_pack_assets))
        self.assertGreaterEqual(int(info.get("builtin_asset_count") or 0), 1)
        self.assertTrue({"vanilla_core", "ruins_pack", "poetry_pack"}.issubset(set(info.get("enabled_packs") or [])))

    def test_conflict_detected_for_equal_priority_cross_pack_collision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_path = temp_path / "asset_registry.json"
            self._write_json(registry_path, {"version": "1.0", "assets": {}})

            pack_a = self._make_pack(
                temp_path,
                pack_id="pack_alpha",
                namespace="shared",
                priority=10,
                assets=[{"asset_id": "gate", "type": "layout", "tags": ["stone"]}],
            )
            pack_b = self._make_pack(
                temp_path,
                pack_id="pack_beta",
                namespace="shared",
                priority=10,
                assets=[{"asset_id": "gate", "type": "layout", "tags": ["history"]}],
            )
            fake_registry = _StaticPackRegistry([pack_a, pack_b])

            with patch("app.core.packs.pack_registry.get_pack_registry", return_value=fake_registry):
                with self.assertRaises(AssetRegistryConflictError):
                    AssetRegistry(registry_path)

    def test_higher_priority_pack_overrides_lower_priority_collision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            registry_path = temp_path / "asset_registry.json"
            self._write_json(registry_path, {"version": "1.0", "assets": {}})

            low_pack = self._make_pack(
                temp_path,
                pack_id="pack_low",
                namespace="shared",
                priority=5,
                assets=[{"asset_id": "gate", "type": "layout", "tags": ["low"]}],
            )
            high_pack = self._make_pack(
                temp_path,
                pack_id="pack_high",
                namespace="shared",
                priority=20,
                assets=[{"asset_id": "gate", "type": "layout", "tags": ["high"]}],
            )
            fake_registry = _StaticPackRegistry([low_pack, high_pack])

            with patch("app.core.packs.pack_registry.get_pack_registry", return_value=fake_registry):
                registry = AssetRegistry(registry_path)

            asset = registry.get("shared:gate")
            self.assertIsInstance(asset, dict)
            self.assertEqual(asset.get("source_pack"), "pack_high")
            self.assertEqual(int(asset.get("priority") or 0), 20)
            self.assertEqual(asset.get("semantic_tags"), ["high"])


if __name__ == "__main__":
    unittest.main()
