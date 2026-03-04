from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.executor.plugin_payload_v2 import build_plugin_payload_v2
from app.core.executor.replay_v2 import replay_payload_v2
from app.core.scene.scene_orchestrator_v2 import compose_scene_and_structure_v2
from tools.replay_evidence_adapter import capture_world_state_snapshot


SCENARIOS = {
    "fog-only": "在湖边制造一个神秘雾气的场景",
    "npc-only": "在湖边放置一个静态守卫",
    "fog+npc": "在湖边制造一个神秘雾气并放置一个静态守卫",
}


def run_once(prompt: str, *, compose_result: dict | None = None) -> dict:
    resolved_compose_result = compose_result if isinstance(compose_result, dict) else compose_scene_and_structure_v2(prompt, strict_mode=False)
    compose_result = resolved_compose_result
    if compose_result.get("status") != "SUCCESS":
        return {
            "compose_status": compose_result.get("status"),
            "compose_failure": compose_result.get("failure_code"),
            "payload_status": "SKIPPED",
            "world_state_hash": "",
            "world_block_count": 0,
        }

    payload = build_plugin_payload_v2(
        compose_result,
        player_id="gate2b_runner",
        strict_mode=False,
    )
    replay = replay_payload_v2(payload)
    snapshot = capture_world_state_snapshot(
        [
            {
                "op": "setblock",
                "x": cmd.get("x"),
                "y": cmd.get("y"),
                "z": cmd.get("z"),
                "block": cmd.get("block"),
            }
            for cmd in (payload.get("commands") or [])
            if isinstance(cmd, dict) and cmd.get("type") == "setblock"
        ]
    )

    return {
        "compose_status": compose_result.get("status"),
        "compose_failure": compose_result.get("failure_code"),
        "mapping_status": (compose_result.get("mapping_result") or {}).get("status"),
        "payload_status": payload.get("version"),
        "merged_hash": ((compose_result.get("merged") or {}).get("hash") or compose_result.get("merge_hash") or ""),
        "final_commands_hash_v2": (payload.get("hash") or {}).get("final_commands") or payload.get("final_commands_hash_v2") or "",
        "replay_status": replay.get("status"),
        "world_state_hash": replay.get("world_state_hash") or snapshot.get("world_state_hash") or "",
        "world_block_count": int(snapshot.get("world_block_count") or 0),
        "world_entity_count": int(replay.get("world_entity_count") or 0),
    }


def run_scenario(name: str, prompt: str, rounds: int) -> dict:
    seed_compose = compose_scene_and_structure_v2(prompt, strict_mode=False)
    rows = [run_once(prompt, compose_result=seed_compose) for _ in range(rounds)]
    world_hash_counter = Counter(item["world_state_hash"] for item in rows)
    merged_hash_counter = Counter(item["merged_hash"] for item in rows)
    final_hash_counter = Counter(item["final_commands_hash_v2"] for item in rows)
    replay_status_counter = Counter(item.get("replay_status") for item in rows)

    unique_world_hashes = sorted(world_hash_counter.keys())
    unique_merged_hashes = sorted(merged_hash_counter.keys())
    unique_final_hashes = sorted(final_hash_counter.keys())

    return {
        "scenario": name,
        "rounds": rounds,
        "unique_world_state_hashes": len(unique_world_hashes),
        "unique_merged_hashes": len(unique_merged_hashes),
        "unique_final_command_hashes": len(unique_final_hashes),
        "replay_status_counts": dict(replay_status_counter),
        "world_state_hash_counts": dict(world_hash_counter),
        "merged_hash_counts": dict(merged_hash_counter),
        "final_command_hash_counts": dict(final_hash_counter),
        "pass": len(unique_world_hashes) == 1 and len(unique_merged_hashes) == 1 and len(unique_final_hashes) == 1 and replay_status_counter.get("SUCCESS", 0) == rounds,
        "sample": rows[0] if rows else {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 2B execution replay determinism checker")
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "docs" / "payload_v2" / "evidence" / "gate2b_execution_replay_report.json"),
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    reports = [run_scenario(name, prompt, args.rounds) for name, prompt in SCENARIOS.items()]
    overall_pass = all(item.get("pass") for item in reports)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "Gate 2B — Execution Replay Determinism",
        "scope": "executor_v2 static summon + replay_v2 deterministic path",
        "rounds_per_scenario": args.rounds,
        "overall_pass": overall_pass,
        "scenarios": reports,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "overall_pass": overall_pass,
        "output": str(output_path),
        "scenarios": [{
            "scenario": item["scenario"],
            "unique_world_state_hashes": item["unique_world_state_hashes"],
            "pass": item["pass"],
        } for item in reports],
    }, ensure_ascii=False))

    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
