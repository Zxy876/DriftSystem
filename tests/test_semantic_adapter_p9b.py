from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.narrative.scene_library import select_fragments_with_debug
from app.core.semantic.semantic_adapter import resolve_semantics


class SemanticAdapterP9BTest(unittest.TestCase):
    def test_resolve_semantics_prefers_vanilla_registry(self):
        result = resolve_semantics("minecraft:lantern")
        self.assertEqual(result.get("source"), "vanilla_registry")
        self.assertIn("light", result.get("semantic_tags") or [])
        self.assertTrue(bool(result.get("adapter_hit")))

    def test_resolve_semantics_supports_mod_map(self):
        result = resolve_semantics("mod:rusted_gear")
        self.assertEqual(result.get("source"), "mod_map")
        tags = result.get("semantic_tags") or []
        self.assertIn("metal", tags)
        self.assertIn("ruin", tags)
        self.assertTrue(bool(result.get("adapter_hit")))

    def test_resolve_semantics_fallback_is_deterministic(self):
        result = resolve_semantics("unknown:item")
        self.assertEqual(result.get("source"), "fallback")
        self.assertEqual(result.get("semantic_tags"), ["unknown:item"])
        self.assertFalse(bool(result.get("adapter_hit")))

    def test_scene_debug_exposes_semantic_resolution(self):
        selection = select_fragments_with_debug(
            {
                "mod:rusted_gear": 1,
                "minecraft:lantern": 1,
            },
            "ruins",
        )

        debug_payload = selection.get("debug") if isinstance(selection.get("debug"), dict) else {}
        semantic_resolution = debug_payload.get("semantic_resolution") if isinstance(debug_payload.get("semantic_resolution"), list) else []
        semantic_source = debug_payload.get("semantic_source") if isinstance(debug_payload.get("semantic_source"), dict) else {}

        self.assertTrue(semantic_resolution)
        self.assertIn("semantic_scores", debug_payload)
        self.assertIn("semantic_adapter_hits", debug_payload)

        mod_row = None
        for row in semantic_resolution:
            if not isinstance(row, dict):
                continue
            if str(row.get("item") or "") == "mod:rusted_gear":
                mod_row = row
                break

        self.assertIsNotNone(mod_row)
        self.assertEqual(mod_row.get("source"), "mod_map")
        self.assertIn("metal", mod_row.get("semantic_tags") or [])
        self.assertTrue(bool(mod_row.get("adapter_hit")))
        self.assertGreaterEqual(int(semantic_source.get("mod_map") or 0), 1)


if __name__ == "__main__":
    unittest.main()
