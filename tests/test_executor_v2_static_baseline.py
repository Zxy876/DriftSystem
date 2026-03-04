from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.executor.canonical_v2 import canonicalize_block_ops, final_commands_hash_v2
from app.core.executor.plugin_payload_v2 import (
    PayloadV2BuildError,
    build_plugin_payload_v2,
    build_plugin_payload_v2_with_trace,
)
from app.core.executor.replay_v2 import replay_payload_v2
from app.core.scene.scene_orchestrator_v2 import compose_scene_and_structure_v2


NPC_ONLY_PROMPT = "在湖边放置一个静态守卫"


class ExecutorV2StaticBaselineTest(unittest.TestCase):
    def test_step1_canonical_block_ops_is_stable(self):
        unsorted_ops = [
            {"x": 3, "y": 65, "z": 2, "block": "oak_planks"},
            {"x": 1, "y": 65, "z": 3, "block": "oak_planks"},
            {"x": 1, "y": 64, "z": 3, "block": "stone"},
        ]
        canonical = canonicalize_block_ops(unsorted_ops)
        self.assertEqual(
            canonical,
            [
                {"type": "setblock", "x": 1, "y": 64, "z": 3, "block": "stone"},
                {"type": "setblock", "x": 1, "y": 65, "z": 3, "block": "oak_planks"},
                {"type": "setblock", "x": 3, "y": 65, "z": 2, "block": "oak_planks"},
            ],
        )

    def test_step2_and_step3_payload_v2_contains_static_summon(self):
        compose_result = compose_scene_and_structure_v2(NPC_ONLY_PROMPT, strict_mode=False)
        self.assertEqual(compose_result.get("status"), "SUCCESS")

        payload = build_plugin_payload_v2(compose_result, player_id="tester", strict_mode=False)
        self.assertEqual(payload.get("version"), "plugin_payload_v2")
        self.assertEqual(payload.get("payload_version"), "v2.1")

        commands = payload.get("commands") or []
        summon_ops = [cmd for cmd in commands if isinstance(cmd, dict) and cmd.get("type") == "summon"]
        self.assertEqual(len(summon_ops), 1)

        summon = summon_ops[0]
        self.assertEqual(summon.get("entity_type"), "villager")
        self.assertEqual(summon.get("no_ai"), True)
        self.assertEqual(summon.get("silent"), True)
        self.assertEqual(summon.get("rotation"), 90)

        setblock_ops = [cmd for cmd in commands if isinstance(cmd, dict) and cmd.get("type") == "setblock"]
        self.assertTrue(all(op.get("block") != "npc_placeholder" for op in setblock_ops))

        hash_field = ((payload.get("hash") or {}).get("final_commands") or "")
        self.assertEqual(hash_field, payload.get("final_commands_hash_v2"))

    def test_anchor_relative_ops_align_with_absolute_commands(self):
        compose_result = compose_scene_and_structure_v2(NPC_ONLY_PROMPT, strict_mode=False)
        self.assertEqual(compose_result.get("status"), "SUCCESS")

        payload = build_plugin_payload_v2(
            compose_result,
            player_id="tester",
            strict_mode=False,
            origin={"base_x": 120, "base_y": 70, "base_z": -30, "anchor_mode": "fixed"},
        )

        self.assertEqual(payload.get("anchor"), "home")
        anchors = payload.get("anchors") or {}
        self.assertEqual((anchors.get("home") or {}).get("base_x"), 120)
        self.assertEqual((anchors.get("home") or {}).get("base_y"), 70)
        self.assertEqual((anchors.get("home") or {}).get("base_z"), -30)

        block_ops = payload.get("block_ops") or []
        commands = payload.get("commands") or []
        setblock_commands = [cmd for cmd in commands if isinstance(cmd, dict) and cmd.get("type") == "setblock"]

        self.assertEqual(len(block_ops), len(setblock_commands))
        self.assertGreater(len(block_ops), 0)

        for block_op, cmd in zip(block_ops, setblock_commands):
            offset = block_op.get("offset") or []
            self.assertEqual(len(offset), 3)
            self.assertEqual(block_op.get("anchor"), "home")
            self.assertEqual(cmd.get("x"), int(offset[0]) + 120)
            self.assertEqual(cmd.get("y"), int(offset[1]) + 70)
            self.assertEqual(cmd.get("z"), int(offset[2]) - 30)
            self.assertEqual(cmd.get("block"), block_op.get("block"))

        entity_ops = payload.get("entity_ops") or []
        summon_commands = [cmd for cmd in commands if isinstance(cmd, dict) and cmd.get("type") == "summon"]
        self.assertEqual(len(entity_ops), len(summon_commands))

        for entity_op, summon in zip(entity_ops, summon_commands):
            offset = entity_op.get("offset") or []
            self.assertEqual(len(offset), 3)
            self.assertEqual(entity_op.get("anchor"), "home")
            self.assertEqual(summon.get("x"), int(offset[0]) + 120)
            self.assertEqual(summon.get("y"), int(offset[1]) + 70)
            self.assertEqual(summon.get("z"), int(offset[2]) - 30)

    def test_multiple_anchors_metadata_and_active_anchor(self):
        compose_result = {
            "status": "SUCCESS",
            "scene_spec": {},
            "scene_patch": {"blocks": []},
            "structure_patch": {"blocks": []},
            "merged": {
                "blocks": [
                    {"x": 1, "y": 64, "z": 1, "block": "stone"},
                ],
                "conflicts_total": 0,
                "spec_dropped_total": 0,
            },
            "mapping_result": {
                "trace": {
                    "rule_version": "rule_v2_2",
                }
            },
        }

        payload = build_plugin_payload_v2(
            compose_result,
            player_id="tester",
            strict_mode=False,
            anchor="scene_zone",
            anchors={
                "home": {"base_x": 100, "base_y": 64, "base_z": 100, "anchor_mode": "fixed"},
                "scene_zone": {"base_x": -300, "base_y": 70, "base_z": 50, "anchor_mode": "fixed"},
                "npc_zone": {"base_x": -280, "base_y": 70, "base_z": 45, "anchor_mode": "fixed"},
            },
        )

        self.assertEqual(payload.get("anchor"), "scene_zone")
        anchors = payload.get("anchors") or {}
        self.assertEqual(sorted(anchors.keys()), ["home", "npc_zone", "scene_zone"])
        self.assertEqual(payload.get("origin"), anchors.get("scene_zone"))

        block_op = (payload.get("block_ops") or [])[0]
        command = [cmd for cmd in (payload.get("commands") or []) if cmd.get("type") == "setblock"][0]
        scene_anchor = anchors.get("scene_zone") or {}

        offset = block_op.get("offset") or []
        self.assertEqual(block_op.get("anchor"), "scene_zone")
        self.assertEqual(command.get("x"), int(offset[0]) + int(scene_anchor.get("base_x")))
        self.assertEqual(command.get("y"), int(offset[1]) + int(scene_anchor.get("base_y")))
        self.assertEqual(command.get("z"), int(offset[2]) + int(scene_anchor.get("base_z")))

    def test_step4_replay_v2_is_deterministic(self):
        compose_result = compose_scene_and_structure_v2(NPC_ONLY_PROMPT, strict_mode=False)
        payload = build_plugin_payload_v2(compose_result, player_id="tester", strict_mode=False)

        first = replay_payload_v2(payload)
        second = replay_payload_v2(payload)

        self.assertEqual(first.get("status"), "SUCCESS")
        self.assertEqual(second.get("status"), "SUCCESS")
        self.assertEqual(first.get("final_commands_hash_v2"), second.get("final_commands_hash_v2"))
        self.assertEqual(first.get("world_state_hash"), second.get("world_state_hash"))

    def test_step5_strict_rejects_multi_entity(self):
        compose_result = {
            "status": "SUCCESS",
            "scene_spec": {},
            "scene_patch": {"blocks": []},
            "structure_patch": {"blocks": []},
            "merged": {
                "blocks": [
                    {"x": 1, "y": 64, "z": 1, "block": "grass_block"},
                    {"x": 2, "y": 64, "z": 1, "block": "npc_placeholder"},
                    {"x": 3, "y": 64, "z": 1, "block": "npc_placeholder"},
                ],
                "conflicts_total": 0,
                "spec_dropped_total": 0,
            },
        }

        with self.assertRaises(PayloadV2BuildError) as captured:
            build_plugin_payload_v2(compose_result, player_id="tester", strict_mode=True)

        self.assertEqual(captured.exception.failure_code, "MULTI_ENTITY_NOT_ALLOWED")

    def test_step5_default_degrades_multi_entity(self):
        compose_result = {
            "status": "SUCCESS",
            "scene_spec": {},
            "scene_patch": {"blocks": []},
            "structure_patch": {"blocks": []},
            "merged": {
                "blocks": [
                    {"x": 1, "y": 64, "z": 1, "block": "grass_block"},
                    {"x": 2, "y": 64, "z": 1, "block": "npc_placeholder"},
                    {"x": 3, "y": 64, "z": 1, "block": "npc_placeholder"},
                ],
                "conflicts_total": 0,
                "spec_dropped_total": 0,
            },
        }

        payload, trace = build_plugin_payload_v2_with_trace(compose_result, player_id="tester", strict_mode=False)
        self.assertEqual(trace.get("status"), "DEGRADED")
        self.assertEqual(trace.get("degrade_reason"), "ENTITY_CAPABILITY_GAP")
        self.assertEqual(trace.get("lost_semantics"), ["npc_behavior.multi_entity"])

        commands = payload.get("commands") or []
        summon_count = len([cmd for cmd in commands if isinstance(cmd, dict) and cmd.get("type") == "summon"])
        self.assertEqual(summon_count, 1)

    def test_hash_v2_is_block_plus_entity(self):
        block_ops = [{"x": 1, "y": 64, "z": 1, "block": "stone"}]
        entity_ops = [
            {
                "type": "summon",
                "entity_type": "villager",
                "x": 2,
                "y": 64,
                "z": 2,
                "name": "Lake Guard",
                "profession": "none",
                "no_ai": True,
                "silent": True,
                "rotation": 90,
            }
        ]
        hash_a = final_commands_hash_v2(block_ops, entity_ops)
        hash_b = final_commands_hash_v2(list(reversed(block_ops)), list(reversed(entity_ops)))
        self.assertEqual(hash_a, hash_b)


if __name__ == "__main__":
    unittest.main()
