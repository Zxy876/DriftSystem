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

from app.core.narrative.scene_library import select_fragments_with_debug
from app.core.packs.pack_types import PackMeta
from app.core.themes.theme_loader import get_theme_registry, reset_theme_registry_cache, theme_registry_info
from app.core.themes.theme_registry import ThemeRegistry, ThemeRegistryConflictError


class _StaticPackRegistry:
    def __init__(self, packs):
        self._packs = list(packs)

    def enabled(self):
        return list(self._packs)


class ThemeRegistryP9C5Test(unittest.TestCase):
    def setUp(self) -> None:
        reset_theme_registry_cache()

    def tearDown(self) -> None:
        reset_theme_registry_cache()

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
        themes_payload: dict,
    ) -> PackMeta:
        pack_dir = base_dir / pack_id
        pack_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(pack_dir / "themes.json", themes_payload)
        return PackMeta(
            pack_id=pack_id,
            version="1.0",
            namespace=namespace,
            priority=priority,
            enabled=True,
            pack_path=str(pack_dir),
        )

    def test_default_registry_merges_builtin_and_pack_themes(self):
        registry = get_theme_registry()
        theme_ids = set(registry.list_themes())

        expected = {
            "wind_camp",
            "market_village",
            "memory_shrine",
            "ruins:ruins_world",
            "poetry:poetry_night",
            "vanilla:vanilla_safe_camp",
        }
        self.assertTrue(expected.issubset(theme_ids))

        info = theme_registry_info()
        self.assertEqual(info.get("version"), "1.0")
        self.assertGreaterEqual(int(info.get("pack_theme_count") or 0), 3)
        self.assertTrue({"vanilla_core", "ruins_pack", "poetry_pack"}.issubset(set(info.get("enabled_packs") or [])))

    def test_conflict_detected_for_equal_priority_pack_theme_collision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            builtin_theme_path = temp_path / "theme_registry.json"
            self._write_json(builtin_theme_path, {"version": "1.0", "themes": []})

            pack_a = self._make_pack(
                temp_path,
                pack_id="pack_alpha",
                namespace="shared",
                priority=10,
                themes_payload={
                    "themes": [
                        {
                            "theme_id": "night_theme",
                            "keywords": ["night"],
                            "allowed_fragments": ["camp"],
                            "bonus_tags": {"light": 1.0},
                            "priority": 10,
                        }
                    ]
                },
            )
            pack_b = self._make_pack(
                temp_path,
                pack_id="pack_beta",
                namespace="shared",
                priority=10,
                themes_payload={
                    "themes": [
                        {
                            "theme_id": "night_theme",
                            "keywords": ["night"],
                            "allowed_fragments": ["village"],
                            "bonus_tags": {"stone": 1.0},
                            "priority": 10,
                        }
                    ]
                },
            )

            fake_registry = _StaticPackRegistry([pack_a, pack_b])
            with patch("app.core.packs.pack_registry.get_pack_registry", return_value=fake_registry):
                with self.assertRaises(ThemeRegistryConflictError):
                    ThemeRegistry(builtin_theme_path=builtin_theme_path)

    def test_higher_priority_pack_theme_overrides_lower_priority(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            builtin_theme_path = temp_path / "theme_registry.json"
            self._write_json(builtin_theme_path, {"version": "1.0", "themes": []})

            low_pack = self._make_pack(
                temp_path,
                pack_id="pack_low",
                namespace="shared",
                priority=5,
                themes_payload={
                    "themes": [
                        {
                            "theme_id": "night_theme",
                            "keywords": ["night"],
                            "allowed_fragments": ["camp"],
                            "bonus_tags": {"light": 1.0},
                            "priority": 5,
                        }
                    ]
                },
            )
            high_pack = self._make_pack(
                temp_path,
                pack_id="pack_high",
                namespace="shared",
                priority=20,
                themes_payload={
                    "themes": [
                        {
                            "theme_id": "night_theme",
                            "keywords": ["night"],
                            "allowed_fragments": ["village"],
                            "bonus_tags": {"stone": 2.0},
                            "priority": 20,
                        }
                    ]
                },
            )

            fake_registry = _StaticPackRegistry([low_pack, high_pack])
            with patch("app.core.packs.pack_registry.get_pack_registry", return_value=fake_registry):
                registry = ThemeRegistry(builtin_theme_path=builtin_theme_path)

            theme = registry.get("shared:night_theme")
            self.assertIsInstance(theme, dict)
            self.assertEqual(theme.get("source_pack"), "pack_high")
            self.assertEqual(int(theme.get("priority") or 0), 20)
            self.assertEqual(theme.get("allowed_fragments"), ["shared:village"])

    def test_scene_selection_applies_theme_filter(self):
        selection = select_fragments_with_debug(
            {
                "bread": 2,
                "oak_log": 1,
            },
            "市集",
        )

        debug_payload = selection.get("debug") if isinstance(selection.get("debug"), dict) else {}
        theme_filter = debug_payload.get("theme_filter") if isinstance(debug_payload.get("theme_filter"), dict) else {}

        self.assertEqual(debug_payload.get("selected_root"), "village")
        self.assertEqual((selection.get("fragments") or [None])[0], "village")
        self.assertTrue(bool(theme_filter.get("applied")))
        self.assertIn("market_village", theme_filter.get("matched_themes") or [])
        self.assertIn("village", theme_filter.get("allowed_fragments") or [])
        self.assertEqual(debug_payload.get("theme_registry_version"), "1.0")


if __name__ == "__main__":
    unittest.main()
