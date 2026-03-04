from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.mapping.v2_mapper import map_scene_v2


class V2MapperTest(unittest.TestCase):
    def setUp(self):
        self.valid_scene_spec = {
            "scene_type": "plain",
            "time_of_day": "day",
            "weather": "clear",
            "mood": "calm",
        }
        self.base_context = {
            "input_text": "test",
            "rule_version": "rule_v2_1",
            "catalog_version": "catalog_v2_1",
            "expected_catalog_version": "catalog_v2_1",
            "engine_version": "engine_v2_1",
            "rule_registry_has_version": True,
            "ruleset_integrity_ok": True,
            "catalog_loaded": True,
            "resource_id": "res/oak",
            "catalog_resource_ids": ["res/oak", "res/spruce"],
            "max_structure_blocks": 100,
            "predicted_blocks": 10,
            "structure_block_count": 10,
            "supported_npc_primitives": {"engine_v2_1": ["patrol", "idle"]},
            "projected_structure_spec": {"type": "house"},
            "mapper_decisions": [{"rule_id": "r1", "priority": 1}],
        }

    def _run_case(self, scene_spec, context):
        first = map_scene_v2(copy.deepcopy(scene_spec), copy.deepcopy(context))
        second = map_scene_v2(copy.deepcopy(scene_spec), copy.deepcopy(context))
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True),
            json.dumps(second, ensure_ascii=False, sort_keys=True),
        )
        return first

    def _assert_trace_required(self, result):
        trace = result.get("trace") or {}
        required = {
            "input_text_hash",
            "scene_spec_hash",
            "rule_version",
            "catalog_version",
            "engine_version",
            "mapper_decisions",
            "final_commands_hash",
        }
        self.assertTrue(required.issubset(set(trace.keys())))

    def test_missing_required_field(self):
        scene_spec = {
            "scene_type": "plain",
            "time_of_day": "day",
            "weather": "clear",
        }
        result = self._run_case(scene_spec, self.base_context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "SCENE_SPEC_INCOMPLETE")
        self._assert_trace_required(result)

    def test_invalid_enum(self):
        scene_spec = dict(self.valid_scene_spec)
        scene_spec["weather"] = "storm"
        result = self._run_case(scene_spec, self.base_context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "SCENE_ENUM_UNSUPPORTED")
        self._assert_trace_required(result)

    def test_ambiguous_top_tie(self):
        context = dict(self.base_context)
        context["top_candidates"] = [
            {"id": "a", "score": 0.9},
            {"id": "b", "score": 0.9},
        ]
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "SCENE_AMBIGUOUS_TOP_TIE")
        self._assert_trace_required(result)

    def test_catalog_unavailable(self):
        context = dict(self.base_context)
        context["catalog_loaded"] = False
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "CATALOG_VERSION_OR_LOAD_FAILED")
        self._assert_trace_required(result)

    def test_resource_not_found(self):
        context = dict(self.base_context)
        context["resource_id"] = "res/missing"
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "RESOURCE_UNRESOLVED")
        self.assertIn("RESOURCE_BINDING.*", result.get("lost_semantics") or [])
        self._assert_trace_required(result)

    def test_ruleset_not_found(self):
        context = dict(self.base_context)
        context["rule_registry_has_version"] = False
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "RULESET_MISSING")
        self._assert_trace_required(result)

    def test_guardrail_violation(self):
        context = dict(self.base_context)
        context["predicted_blocks"] = 120
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "RESOURCE_GUARDRAIL_BLOCKED")
        self._assert_trace_required(result)

    def test_projection_unsupported(self):
        context = dict(self.base_context)
        context["unsupported_semantics"] = ["ATMOSPHERE.fog"]
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "NON_PROJECTABLE_SCENE_EFFECT")
        self._assert_trace_required(result)

    def test_npc_primitive_unsupported(self):
        context = dict(self.base_context)
        context["requested_npc_primitive"] = "patrol_and_react"
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "NPC_PRIMITIVE_UNSUPPORTED")
        self._assert_trace_required(result)

    def test_structure_too_large(self):
        context = dict(self.base_context)
        context["structure_block_count"] = 150
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "STRUCTURE_TOO_LARGE")
        self.assertIsNone(result.get("degrade_reason"))
        self._assert_trace_required(result)

    def test_merge_conflict_unresolved(self):
        context = dict(self.base_context)
        context["exists_conflict"] = True
        context["conflict_priority_equal"] = True
        context["tiebreak_rule_found"] = False
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertEqual(result.get("failure_code"), "NONE")
        self.assertEqual(result.get("degrade_reason"), "CONFLICT_NO_TIEBREAKER")
        self._assert_trace_required(result)

    def test_validator_failure(self):
        context = dict(self.base_context)
        context["validator_result"] = {"failure_code": "INVALID_BLOCK_ID"}
        result = self._run_case(self.valid_scene_spec, context)

        self.assertEqual(result.get("status"), "REJECTED")
        self.assertEqual(result.get("failure_code"), "INVALID_BLOCK_ID")
        self.assertIsNone(result.get("degrade_reason"))
        self._assert_trace_required(result)


if __name__ == "__main__":
    unittest.main()
