from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.scene.scene_llm_v1 import generate_scene_spec_from_text_v1
from app.core.scene.scene_orchestrator_v2 import compose_scene_and_structure_v2


PROMPT = "在湖边制造一个神秘雾气与低沉音乐的场景"


class SceneSemanticPhase18Test(unittest.TestCase):
    def test_semantic_effects_structure_stable(self):
        result = generate_scene_spec_from_text_v1(PROMPT)
        self.assertEqual(result.get("status"), "VALID")

        spec = result.get("scene_spec") or {}
        self.assertEqual(spec.get("semantic_version"), "scene_semantic_v1")
        self.assertEqual(
            spec.get("semantic_effects"),
            [
                {
                    "type": "atmosphere",
                    "value": "fog",
                    "confidence": 0.9,
                    "effect_source": "nl_extraction",
                },
                {
                    "type": "sound",
                    "value": "low_music",
                    "confidence": 0.8,
                    "effect_source": "nl_extraction",
                },
            ],
        )

    def test_repeated_hash_is_stable(self):
        hashes = []
        for _ in range(5):
            result = generate_scene_spec_from_text_v1(PROMPT)
            payload = json.dumps(result.get("scene_spec") or {}, ensure_ascii=False, sort_keys=True)
            hashes.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())

        self.assertTrue(all(value == hashes[0] for value in hashes))

    def test_default_mode_projects_fog_and_keeps_music_lost(self):
        result = compose_scene_and_structure_v2(PROMPT, strict_mode=False)
        self.assertEqual(result.get("status"), "SUCCESS")

        mapping_result = result.get("mapping_result") or {}
        self.assertEqual(mapping_result.get("status"), "OK")
        self.assertIsNone(mapping_result.get("degrade_reason"))
        self.assertEqual(
            mapping_result.get("lost_semantics"),
            ["sound.low_music"],
        )

        trace = mapping_result.get("trace") or {}
        decisions = trace.get("mapper_decisions") or []
        self.assertTrue(any(item.get("rule_id") == "PROJECTION_ATMOSPHERE_FOG_V1" for item in decisions if isinstance(item, dict)))
        self.assertGreater(result.get("scene_block_count", 0), 0)

    def test_strict_mode_rejects_unsupported_effects(self):
        result = compose_scene_and_structure_v2(PROMPT, strict_mode=True)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "EXEC_CAPABILITY_GAP")

        mapping_result = result.get("mapping_result") or {}
        self.assertEqual(mapping_result.get("status"), "REJECTED")
        self.assertEqual(mapping_result.get("failure_code"), "EXEC_CAPABILITY_GAP")
        self.assertEqual(mapping_result.get("lost_semantics"), ["sound.low_music"])


if __name__ == "__main__":
    unittest.main()
