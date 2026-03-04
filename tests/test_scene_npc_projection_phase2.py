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


NPC_ONLY_PROMPT = "在湖边放置一个静态守卫"
NPC_MUSIC_PROMPT = "在湖边放置一个静态守卫并加入低沉音乐"


class SceneNpcProjectionPhase2Test(unittest.TestCase):
    def test_npc_only_default_is_ok_with_projection(self):
        result = compose_scene_and_structure_v2(NPC_ONLY_PROMPT, strict_mode=False)

        self.assertEqual(result.get("status"), "SUCCESS")

        mapping_result = result.get("mapping_result") or {}
        self.assertEqual(mapping_result.get("status"), "OK")
        self.assertEqual(mapping_result.get("lost_semantics"), [])

        decisions = ((mapping_result.get("trace") or {}).get("mapper_decisions") or [])
        npc_decision = next(
            (
                item
                for item in decisions
                if isinstance(item, dict) and item.get("rule_id") == "PROJECTION_NPC_LAKE_GUARD_V1"
            ),
            None,
        )
        self.assertIsNotNone(npc_decision)
        self.assertEqual(npc_decision.get("priority"), 350)
        self.assertEqual(npc_decision.get("effect"), "npc_behavior.lake_guard")
        self.assertEqual(npc_decision.get("entity_type"), "villager")
        self.assertEqual(npc_decision.get("ai_disabled"), True)
        self.assertEqual(npc_decision.get("silent"), True)
        self.assertGreaterEqual(int(npc_decision.get("projection_blocks_added") or 0), 0)
        self.assertGreater(int(result.get("scene_block_count") or 0), 0)

    def test_npc_music_default_keeps_ok_and_loses_music_only(self):
        result = compose_scene_and_structure_v2(NPC_MUSIC_PROMPT, strict_mode=False)

        self.assertEqual(result.get("status"), "SUCCESS")

        mapping_result = result.get("mapping_result") or {}
        self.assertEqual(mapping_result.get("status"), "OK")
        self.assertEqual(mapping_result.get("failure_code"), "NONE")
        self.assertEqual(mapping_result.get("lost_semantics"), ["sound.low_music"])

        self.assertGreater(int(result.get("scene_block_count") or 0), 0)

    def test_npc_music_strict_rejects_with_exec_gap(self):
        result = compose_scene_and_structure_v2(NPC_MUSIC_PROMPT, strict_mode=True)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "EXEC_CAPABILITY_GAP")

        mapping_result = result.get("mapping_result") or {}
        self.assertEqual(mapping_result.get("status"), "REJECTED")
        self.assertEqual(mapping_result.get("failure_code"), "EXEC_CAPABILITY_GAP")
        self.assertEqual(mapping_result.get("lost_semantics"), ["sound.low_music"])


if __name__ == "__main__":
    unittest.main()
