from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.executor.canonical_v2 import final_commands_hash_v2
from app.core.executor.plugin_payload_v1 import build_plugin_payload_v1
from app.core.executor.plugin_payload_v2 import build_plugin_payload_v2
from app.core.scene.scene_orchestrator_v1 import compose_scene_and_structure
from app.core.scene.scene_orchestrator_v2 import compose_scene_and_structure_v2


SCENARIOS = {
    "fog-only": "在湖边制造一个神秘雾气的场景",
    "npc-only": "在湖边放置一个静态守卫",
    "fog+npc": "在湖边制造一个神秘雾气并放置一个静态守卫",
}


def _canonical_permutation_invariant(payload_v2: dict) -> bool:
    commands = payload_v2.get("commands") or []
    block_ops = []
    entity_ops = []
    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        if cmd.get("type") == "setblock":
            block_ops.append({
                "x": cmd.get("x"),
                "y": cmd.get("y"),
                "z": cmd.get("z"),
                "block": cmd.get("block"),
            })
        elif cmd.get("type") == "summon":
            entity_ops.append({
                "type": "summon",
                "entity_type": cmd.get("entity_type"),
                "x": cmd.get("x"),
                "y": cmd.get("y"),
                "z": cmd.get("z"),
                "name": cmd.get("name"),
                "profession": cmd.get("profession"),
                "no_ai": cmd.get("no_ai"),
                "silent": cmd.get("silent"),
                "rotation": cmd.get("rotation"),
            })

    baseline = final_commands_hash_v2(block_ops, entity_ops)
    for _ in range(20):
        random.shuffle(block_ops)
        random.shuffle(entity_ops)
        if final_commands_hash_v2(block_ops, entity_ops) != baseline:
            return False
    return True


def run_scenario(name: str, prompt: str, rounds: int) -> dict:
    compose_v1 = compose_scene_and_structure(prompt)
    compose_v2 = compose_scene_and_structure_v2(prompt, strict_mode=False)

    if compose_v1.get("status") != "SUCCESS" or compose_v2.get("status") != "SUCCESS":
        return {
            "scenario": name,
            "rounds": rounds,
            "pass": False,
            "compose_v1_status": compose_v1.get("status"),
            "compose_v2_status": compose_v2.get("status"),
            "compose_v1_failure": compose_v1.get("failure_code"),
            "compose_v2_failure": compose_v2.get("failure_code"),
        }

    v1_rows = [build_plugin_payload_v1(compose_v1, player_id="gate3_runner") for _ in range(rounds)]
    v2_rows = [build_plugin_payload_v2(compose_v2, player_id="gate3_runner", strict_mode=False) for _ in range(rounds)]

    v1_hashes = [((row.get("hash") or {}).get("merged_blocks") or "") for row in v1_rows]
    v2_hashes = [((row.get("hash") or {}).get("final_commands") or "") for row in v2_rows]

    v1_counter = Counter(v1_hashes)
    v2_counter = Counter(v2_hashes)

    cross_confused = any(v1_hashes[idx] == v2_hashes[idx] for idx in range(min(len(v1_hashes), len(v2_hashes))))
    canonical_ok = _canonical_permutation_invariant(v2_rows[0]) if v2_rows else False

    pass_flag = (
        len(v1_counter.keys()) == 1
        and len(v2_counter.keys()) == 1
        and not cross_confused
        and canonical_ok
    )

    return {
        "scenario": name,
        "rounds": rounds,
        "v1_unique_hashes": len(v1_counter.keys()),
        "v2_unique_hashes": len(v2_counter.keys()),
        "cross_version_confused": cross_confused,
        "canonical_permutation_invariant": canonical_ok,
        "v1_hash_counts": dict(v1_counter),
        "v2_hash_counts": dict(v2_counter),
        "pass": pass_flag,
        "sample": {
            "v1_hash": v1_hashes[0] if v1_hashes else "",
            "v2_hash": v2_hashes[0] if v2_hashes else "",
            "v1_payload_version": v1_rows[0].get("version") if v1_rows else "",
            "v2_payload_version": v2_rows[0].get("version") if v2_rows else "",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 3 hash consistency checker")
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "docs" / "payload_v2" / "evidence" / "gate3_hash_consistency_report.json"),
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    reports = [run_scenario(name, prompt, args.rounds) for name, prompt in SCENARIOS.items()]
    overall_pass = all(item.get("pass") for item in reports)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "Gate 3 — Hash Consistency",
        "scope": "v1 merged_blocks hash stability + v2 final_commands hash stability + cross-version non-confusion",
        "rounds_per_scenario": args.rounds,
        "overall_pass": overall_pass,
        "scenarios": reports,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "overall_pass": overall_pass,
        "output": str(output_path),
        "scenarios": [
            {
                "scenario": item.get("scenario"),
                "v1_unique_hashes": item.get("v1_unique_hashes"),
                "v2_unique_hashes": item.get("v2_unique_hashes"),
                "cross_version_confused": item.get("cross_version_confused"),
                "pass": item.get("pass"),
            }
            for item in reports
        ],
    }, ensure_ascii=False))

    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
