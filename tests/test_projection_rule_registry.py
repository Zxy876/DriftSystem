from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.mapping.projection_rule_registry import (
    DEFAULT_RULE_VERSION,
    get_projection_rule,
    list_supported_projection_effects,
    projection_supported,
)


class ProjectionRuleRegistryTest(unittest.TestCase):
    def test_fog_rule_is_frozen_under_rule_version(self):
        self.assertEqual(DEFAULT_RULE_VERSION, "rule_v2_2")

        fog_rule = get_projection_rule("rule_v2_2", "atmosphere.fog")
        self.assertIsNotNone(fog_rule)
        self.assertEqual(fog_rule.get("rule_id"), "PROJECTION_ATMOSPHERE_FOG_V1")
        self.assertEqual(fog_rule.get("priority"), 300)
        self.assertEqual(fog_rule.get("block"), "glass_pane")
        self.assertEqual(fog_rule.get("y_offset"), 1)
        self.assertEqual(fog_rule.get("fill_mode"), "full")
        self.assertEqual(fog_rule.get("conflict_policy"), "skip_on_structure")

    def test_projection_supported_is_version_and_engine_bound(self):
        self.assertTrue(projection_supported("rule_v2_2", "engine_v2_1", "atmosphere.fog"))
        self.assertTrue(projection_supported("rule_v2_2", "engine_v2_1", "npc_behavior.lake_guard"))
        self.assertFalse(projection_supported("rule_v2_2", "engine_v3_0", "atmosphere.fog"))
        self.assertFalse(projection_supported("rule_v2_2", "engine_v2_1", "sound.low_music"))

    def test_supported_effects_list_is_deterministic(self):
        effects_a = list_supported_projection_effects("rule_v2_2", "engine_v2_1")
        effects_b = list_supported_projection_effects("rule_v2_2", "engine_v2_1")
        self.assertEqual(effects_a, effects_b)
        self.assertEqual(effects_a, ["atmosphere.fog", "npc_behavior.lake_guard"])


if __name__ == "__main__":
    unittest.main()
