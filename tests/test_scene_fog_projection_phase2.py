from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.scene.scene_orchestrator_v2 import compose_scene_and_structure_v2


FOG_ONLY_PROMPT = "在湖边制造一个神秘雾气的场景"
FOG_MUSIC_PROMPT = "在湖边制造一个神秘雾气与低沉音乐的场景"


class SceneFogProjectionPhase2Test(unittest.TestCase):
    def test_fog_only_is_projected_with_ok_status(self):
        result = compose_scene_and_structure_v2(FOG_ONLY_PROMPT, strict_mode=False)

        self.assertEqual(result.get("status"), "SUCCESS")

        mapping_result = result.get("mapping_result") or {}
        self.assertEqual(mapping_result.get("status"), "OK")
        self.assertEqual(mapping_result.get("lost_semantics"), [])
        self.assertIsNone(mapping_result.get("degrade_reason"))

        self.assertGreater(int(result.get("scene_block_count") or 0), 0)

        decisions = ((mapping_result.get("trace") or {}).get("mapper_decisions") or [])
        fog_decision = next(
            (
                item
                for item in decisions
                if isinstance(item, dict) and item.get("rule_id") == "PROJECTION_ATMOSPHERE_FOG_V1"
            ),
            None,
        )
        self.assertIsNotNone(fog_decision)
        self.assertEqual(fog_decision.get("priority"), 300)
        self.assertEqual(fog_decision.get("effect"), "atmosphere.fog")
        self.assertGreater(int(fog_decision.get("projection_blocks_added") or 0), 0)
        self.assertGreaterEqual(int(fog_decision.get("conflict_blocks_skipped") or 0), 0)

    def test_fog_music_default_keeps_ok_and_loses_music_only(self):
        result = compose_scene_and_structure_v2(FOG_MUSIC_PROMPT, strict_mode=False)

        self.assertEqual(result.get("status"), "SUCCESS")

        mapping_result = result.get("mapping_result") or {}
        self.assertEqual(mapping_result.get("status"), "OK")
        self.assertEqual(mapping_result.get("failure_code"), "NONE")
        self.assertEqual(mapping_result.get("lost_semantics"), ["sound.low_music"])

        self.assertGreater(int(result.get("scene_block_count") or 0), 0)

    def test_fog_music_strict_rejects_with_exec_gap(self):
        result = compose_scene_and_structure_v2(FOG_MUSIC_PROMPT, strict_mode=True)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "EXEC_CAPABILITY_GAP")

        mapping_result = result.get("mapping_result") or {}
        self.assertEqual(mapping_result.get("status"), "REJECTED")
        self.assertEqual(mapping_result.get("failure_code"), "EXEC_CAPABILITY_GAP")
        self.assertEqual(mapping_result.get("lost_semantics"), ["sound.low_music"])


if __name__ == "__main__":
    unittest.main()
