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

from app.core.executor.plugin_payload_v1 import build_plugin_payload_v1
from app.core.scene.scene_orchestrator_v1 import compose_scene_and_structure


class PluginPayloadV1Test(unittest.TestCase):
    def test_payload_deterministic_for_fixed_prompt(self):
        prompt = "平静夜晚的湖边，建一个7x5木屋"
        runs = [
            build_plugin_payload_v1(
                compose_scene_and_structure(prompt),
                player_id="player_1",
            )
            for _ in range(5)
        ]

        self.assertTrue(all(payload.get("version") == "plugin_payload_v1" for payload in runs))
        self.assertTrue(all((payload.get("commands") or []) for payload in runs))

        payload_hashes = []
        for payload in runs:
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            payload_hashes.append(hashlib.sha256(encoded.encode("utf-8")).hexdigest())

        self.assertTrue(all(d == payload_hashes[0] for d in payload_hashes))

        sample = runs[0]
        print(f"commands_count={len(sample.get('commands') or [])}")
        print(f"payload_merged_blocks_hash={sample.get('hash', {}).get('merged_blocks', '')}")
        print(f"build_id={sample.get('build_id', '')}")

    def test_origin_offset_applied_to_commands(self):
        prompt = "平静夜晚的湖边，建一个7x5木屋"
        compose_result = compose_scene_and_structure(prompt)

        baseline = build_plugin_payload_v1(
            compose_result,
            player_id="player_1",
            origin={"base_x": 0, "base_y": 0, "base_z": 0, "anchor_mode": "fixed"},
        )
        shifted = build_plugin_payload_v1(
            compose_result,
            player_id="player_1",
            origin={"base_x": 10, "base_y": 0, "base_z": 0, "anchor_mode": "fixed"},
        )

        baseline_commands = baseline.get("commands") or []
        shifted_commands = shifted.get("commands") or []

        self.assertEqual(len(baseline_commands), len(shifted_commands))
        self.assertTrue(len(baseline_commands) > 0)

        for before, after in zip(baseline_commands, shifted_commands):
            self.assertEqual(after["x"], before["x"] + 10)
            self.assertEqual(after["y"], before["y"])
            self.assertEqual(after["z"], before["z"])
            self.assertEqual(after["block"], before["block"])

    def test_build_id_is_stable_for_same_input_and_origin(self):
        prompt = "平静夜晚的湖边，建一个7x5木屋"
        compose_result = compose_scene_and_structure(prompt)

        first = build_plugin_payload_v1(
            compose_result,
            player_id="player_1",
            origin={"base_x": 0, "base_y": 64, "base_z": 0, "anchor_mode": "fixed"},
        )
        second = build_plugin_payload_v1(
            compose_result,
            player_id="player_1",
            origin={"base_x": 0, "base_y": 64, "base_z": 0, "anchor_mode": "fixed"},
        )

        self.assertEqual(first.get("build_id"), second.get("build_id"))


if __name__ == "__main__":
    unittest.main()
