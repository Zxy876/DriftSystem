from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.mapping.projection_rule_registry import DEFAULT_RULE_VERSION, PROJECTION_RULE_REGISTRY
from app.core.mapping.rule_immutability_guard import evaluate_rule_immutability


FREEZE_SNAPSHOT_PATH = BACKEND_ROOT / "app" / "core" / "mapping" / "projection_rule_registry_freeze.json"


class Gate6RuleImmutabilityTest(unittest.TestCase):
    def setUp(self):
        self.freeze_snapshot = json.loads(FREEZE_SNAPSHOT_PATH.read_text(encoding="utf-8"))

    def test_current_registry_passes_immutability_guard(self):
        result = evaluate_rule_immutability(
            default_rule_version=DEFAULT_RULE_VERSION,
            registry=deepcopy(PROJECTION_RULE_REGISTRY),
            freeze_snapshot=deepcopy(self.freeze_snapshot),
        )
        self.assertEqual(result.get("status"), "PASS")
        self.assertEqual(result.get("failure_codes"), [])

    def test_mutating_frozen_rule_fails(self):
        mutated_registry = deepcopy(PROJECTION_RULE_REGISTRY)
        mutated_registry["rule_v2_2"]["atmosphere.fog"]["y_offset"] = 99

        result = evaluate_rule_immutability(
            default_rule_version="rule_v2_2",
            registry=mutated_registry,
            freeze_snapshot=deepcopy(self.freeze_snapshot),
        )
        self.assertEqual(result.get("status"), "FAIL")
        self.assertIn("FROZEN_RULE_MUTATED", result.get("failure_codes") or [])

    def test_registry_changed_without_version_bump_fails(self):
        changed_registry = deepcopy(PROJECTION_RULE_REGISTRY)
        changed_registry["rule_v2_3"] = deepcopy(changed_registry["rule_v2_2"])

        result = evaluate_rule_immutability(
            default_rule_version="rule_v2_2",
            registry=changed_registry,
            freeze_snapshot=deepcopy(self.freeze_snapshot),
        )
        self.assertEqual(result.get("status"), "FAIL")
        self.assertIn("RULE_VERSION_NOT_BUMPED", result.get("failure_codes") or [])

    def test_registry_changed_with_version_bump_passes(self):
        changed_registry = deepcopy(PROJECTION_RULE_REGISTRY)
        changed_registry["rule_v2_3"] = deepcopy(changed_registry["rule_v2_2"])
        changed_registry["rule_v2_3"]["npc_behavior.lake_guard"]["z_offset"] = 1

        result = evaluate_rule_immutability(
            default_rule_version="rule_v2_3",
            registry=changed_registry,
            freeze_snapshot=deepcopy(self.freeze_snapshot),
        )
        self.assertEqual(result.get("status"), "PASS")
        self.assertEqual(result.get("failure_codes"), [])


if __name__ == "__main__":
    unittest.main()
