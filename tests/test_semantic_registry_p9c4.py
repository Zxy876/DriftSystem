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

from app.core.semantic.semantic_adapter import resolve_semantics, reset_semantic_cache
from app.core.semantic.semantic_registry import (
    SemanticRegistry,
    SemanticRegistryConflictError,
    get_semantic_registry,
    reset_semantic_registry_cache,
    semantic_registry_info,
)
from app.core.packs.pack_types import PackMeta


class _StaticPackRegistry:
    def __init__(self, packs):
        self._packs = list(packs)

    def enabled(self):
        return list(self._packs)


class SemanticRegistryP9C4Test(unittest.TestCase):
    def setUp(self) -> None:
        reset_semantic_cache()
        reset_semantic_registry_cache()

    def tearDown(self) -> None:
        reset_semantic_cache()
        reset_semantic_registry_cache()

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
        semantic_map: dict,
    ) -> PackMeta:
        pack_dir = base_dir / pack_id
        pack_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(pack_dir / "semantic_map.json", semantic_map)
        return PackMeta(
            pack_id=pack_id,
            version="1.0",
            namespace=namespace,
            priority=priority,
            enabled=True,
            pack_path=str(pack_dir),
        )

    def test_default_registry_merges_pack_semantic_maps(self):
        registry = get_semantic_registry()
        resolved = registry.resolve("poetry:moon_verse")

        self.assertIsInstance(resolved, dict)
        self.assertEqual(resolved.get("source"), "pack:poetry_pack")
        self.assertIn("emotion", resolved.get("semantic_tags") or [])
        self.assertIn("memory", resolved.get("semantic_tags") or [])

        info = semantic_registry_info()
        self.assertEqual(info.get("version"), "1.0")
        self.assertGreaterEqual(int(info.get("pack_count") or 0), 1)
        self.assertTrue({"vanilla_core", "ruins_pack", "poetry_pack"}.issubset(set(info.get("enabled_packs") or [])))

    def test_semantic_adapter_resolves_pack_source(self):
        result = resolve_semantics("poetry:moon_verse")
        self.assertEqual(result.get("source"), "pack:poetry_pack")
        self.assertIn("ritual", result.get("semantic_tags") or [])
        self.assertTrue(bool(result.get("adapter_hit")))

    def test_conflict_detected_for_equal_priority_pack_collision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            vanilla_path = temp_path / "vanilla.json"
            mod_path = temp_path / "mod.json"
            sources_path = temp_path / "sources.json"

            self._write_json(vanilla_path, {})
            self._write_json(mod_path, {})
            self._write_json(
                sources_path,
                {
                    "version": "1.0",
                    "sources": {
                        "vanilla_registry": {"priority": 1},
                        "mod_map": {"priority": 2},
                        "pack_map": {"priority": 0},
                        "fallback": {"priority": 3},
                    },
                },
            )

            pack_a = self._make_pack(
                temp_path,
                pack_id="pack_alpha",
                namespace="shared",
                priority=10,
                semantic_map={"ritual_token": ["ritual"]},
            )
            pack_b = self._make_pack(
                temp_path,
                pack_id="pack_beta",
                namespace="shared",
                priority=10,
                semantic_map={"ritual_token": ["memory"]},
            )

            fake_pack_registry = _StaticPackRegistry([pack_a, pack_b])
            with patch("app.core.packs.pack_registry.get_pack_registry", return_value=fake_pack_registry):
                with self.assertRaises(SemanticRegistryConflictError):
                    SemanticRegistry(
                        vanilla_path=vanilla_path,
                        mod_map_path=mod_path,
                        sources_path=sources_path,
                    )

    def test_higher_priority_pack_overrides_lower_priority(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            vanilla_path = temp_path / "vanilla.json"
            mod_path = temp_path / "mod.json"
            sources_path = temp_path / "sources.json"

            self._write_json(vanilla_path, {})
            self._write_json(mod_path, {})
            self._write_json(
                sources_path,
                {
                    "version": "1.0",
                    "sources": {
                        "vanilla_registry": {"priority": 1},
                        "mod_map": {"priority": 2},
                        "pack_map": {"priority": 0},
                        "fallback": {"priority": 3},
                    },
                },
            )

            low_pack = self._make_pack(
                temp_path,
                pack_id="pack_low",
                namespace="shared",
                priority=5,
                semantic_map={"ritual_token": ["low"]},
            )
            high_pack = self._make_pack(
                temp_path,
                pack_id="pack_high",
                namespace="shared",
                priority=20,
                semantic_map={"ritual_token": ["high"]},
            )

            fake_pack_registry = _StaticPackRegistry([low_pack, high_pack])
            with patch("app.core.packs.pack_registry.get_pack_registry", return_value=fake_pack_registry):
                registry = SemanticRegistry(
                    vanilla_path=vanilla_path,
                    mod_map_path=mod_path,
                    sources_path=sources_path,
                )

            resolved = registry.resolve("shared:ritual_token")
            self.assertIsInstance(resolved, dict)
            self.assertEqual(resolved.get("source"), "pack:pack_high")
            self.assertEqual(resolved.get("semantic_tags"), ["high"])


if __name__ == "__main__":
    unittest.main()
