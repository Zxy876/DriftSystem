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

from app.core.fragments.fragment_loader import fragment_registry_info, get_fragment_registry, reset_fragment_registry_cache
from app.core.fragments.fragment_registry import FragmentRegistry, FragmentRegistryConflictError
from app.core.narrative import scene_library
from app.core.packs.pack_types import PackMeta


class _StaticPackRegistry:
    def __init__(self, packs):
        self._packs = list(packs)

    def enabled(self):
        return list(self._packs)


class FragmentRegistryP9C3Test(unittest.TestCase):
    def setUp(self) -> None:
        reset_fragment_registry_cache()
        scene_library._load_fragments.cache_clear()

    def tearDown(self) -> None:
        scene_library._load_fragments.cache_clear()

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
        fragments: list[dict],
    ) -> PackMeta:
        pack_dir = base_dir / pack_id
        pack_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(pack_dir / "fragments.json", {"fragments": fragments})
        return PackMeta(
            pack_id=pack_id,
            version="1.0",
            namespace=namespace,
            priority=priority,
            enabled=True,
            pack_path=str(pack_dir),
        )

    def test_default_registry_merges_pack_fragments(self):
        registry = get_fragment_registry()
        fragment_ids = set(registry.list_fragments())

        expected_pack_fragments = {
            "vanilla:camp_storage_ext",
            "ruins:ruins_arch",
            "poetry:echo_stage",
        }
        self.assertTrue(expected_pack_fragments.issubset(fragment_ids))

        info = fragment_registry_info()
        self.assertGreaterEqual(int(info.get("pack_fragment_count") or 0), len(expected_pack_fragments))
        self.assertGreaterEqual(int(info.get("builtin_fragment_count") or 0), 1)
        self.assertTrue({"vanilla_core", "ruins_pack", "poetry_pack"}.issubset(set(info.get("enabled_packs") or [])))

    def test_conflict_detected_for_equal_priority_cross_pack_collision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            builtin_dir = temp_path / "builtin_fragments"
            builtin_dir.mkdir(parents=True, exist_ok=True)

            pack_a = self._make_pack(
                temp_path,
                pack_id="pack_alpha",
                namespace="shared",
                priority=10,
                fragments=[
                    {
                        "fragment_id": "gate",
                        "root": False,
                        "priority": 10,
                        "tags": ["stone"],
                        "requires": ["stone"],
                    }
                ],
            )
            pack_b = self._make_pack(
                temp_path,
                pack_id="pack_beta",
                namespace="shared",
                priority=10,
                fragments=[
                    {
                        "fragment_id": "gate",
                        "root": False,
                        "priority": 10,
                        "tags": ["history"],
                        "requires": ["history"],
                    }
                ],
            )

            fake_registry = _StaticPackRegistry([pack_a, pack_b])
            with patch("app.core.packs.pack_registry.get_pack_registry", return_value=fake_registry):
                with self.assertRaises(FragmentRegistryConflictError):
                    FragmentRegistry(builtin_fragments_dir=builtin_dir)

    def test_higher_priority_pack_overrides_lower_priority_collision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            builtin_dir = temp_path / "builtin_fragments"
            builtin_dir.mkdir(parents=True, exist_ok=True)

            low_pack = self._make_pack(
                temp_path,
                pack_id="pack_low",
                namespace="shared",
                priority=5,
                fragments=[
                    {
                        "fragment_id": "gate",
                        "root": False,
                        "priority": 5,
                        "tags": ["low"],
                        "requires": ["low"],
                    }
                ],
            )
            high_pack = self._make_pack(
                temp_path,
                pack_id="pack_high",
                namespace="shared",
                priority=20,
                fragments=[
                    {
                        "fragment_id": "gate",
                        "root": False,
                        "priority": 20,
                        "tags": ["high"],
                        "requires": ["high"],
                    }
                ],
            )

            fake_registry = _StaticPackRegistry([low_pack, high_pack])
            with patch("app.core.packs.pack_registry.get_pack_registry", return_value=fake_registry):
                registry = FragmentRegistry(builtin_fragments_dir=builtin_dir)

            fragment = registry.get("shared:gate")
            self.assertIsInstance(fragment, dict)
            self.assertEqual(fragment.get("source_pack"), "pack_high")
            self.assertEqual(int(fragment.get("priority") or 0), 20)
            self.assertEqual(fragment.get("tags"), ["high"])

    def test_scene_library_uses_merged_fragment_registry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            builtin_dir = temp_path / "builtin_fragments"
            self._write_json(
                builtin_dir / "camp.json",
                {
                    "id": "camp",
                    "root": True,
                    "priority": 10,
                    "tags": ["wood"],
                    "requires": ["wood"],
                    "connections": [],
                    "events": [
                        {
                            "event_id": "spawn_builtin_camp",
                            "type": "spawn_structure",
                            "anchor_ref": "player",
                            "data": {"template": "camp_small"},
                        }
                    ],
                },
            )

            moon_pack = self._make_pack(
                temp_path,
                pack_id="moon_pack",
                namespace="moon",
                priority=50,
                fragments=[
                    {
                        "fragment_id": "moon_camp",
                        "root": True,
                        "priority": 90,
                        "tags": ["wood", "moon"],
                        "requires": ["wood"],
                        "connections": [],
                        "events": [
                            {
                                "event_id": "spawn_moon_camp",
                                "type": "spawn_structure",
                                "anchor_ref": "player",
                                "data": {"template": "moon_camp"},
                            }
                        ],
                    }
                ],
            )

            fake_pack_registry = _StaticPackRegistry([moon_pack])
            with patch("app.core.packs.pack_registry.get_pack_registry", return_value=fake_pack_registry):
                merged_registry = FragmentRegistry(builtin_fragments_dir=builtin_dir)

            with patch("app.core.fragments.fragment_loader.get_fragment_registry", return_value=merged_registry):
                scene_library._load_fragments.cache_clear()
                selection = scene_library.select_fragments_with_debug({"wood": 1}, "")

            debug_payload = selection.get("debug") if isinstance(selection.get("debug"), dict) else {}
            self.assertEqual(debug_payload.get("selected_root"), "moon:moon_camp")
            self.assertEqual(selection.get("fragments"), ["moon:moon_camp"])


if __name__ == "__main__":
    unittest.main()
