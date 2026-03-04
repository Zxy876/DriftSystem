from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.executor.executor_v1 import execute_payload_v1
from app.core.executor.plugin_payload_v1 import build_plugin_payload_v1
from app.core.executor.plugin_payload_v2 import build_plugin_payload_v2
from app.core.executor.replay_v1 import replay_payload_v1


def _compose_fixture(*, with_npc: bool) -> dict:
    blocks = [
        {"x": 0, "y": 64, "z": 0, "block": "grass_block"},
        {"x": 1, "y": 64, "z": 0, "block": "oak_planks"},
    ]
    if with_npc:
        blocks.append({"x": 2, "y": 64, "z": 0, "block": "npc_placeholder"})

    return {
        "status": "SUCCESS",
        "failure_code": "NONE",
        "scene_spec": {"scene_type": "lake", "time_of_day": "night", "weather": "clear", "mood": "calm"},
        "scene_patch": {"build_status": "SUCCESS", "failure_code": "NONE", "blocks": []},
        "structure_patch": {"build_status": "SUCCESS", "failure_code": "NONE", "blocks": blocks},
        "merged": {
            "status": "SUCCESS",
            "failure_code": "NONE",
            "blocks": blocks,
            "conflicts_total": 0,
            "spec_dropped_total": 0,
        },
        "validation": {"status": "VALID", "failure_code": "NONE"},
        "scene_block_count": 0,
        "spec_block_count": len(blocks),
        "merged_block_count": len(blocks),
        "merge_hash": "",
        "mapping_result": {
            "trace": {
                "rule_version": "rule_v2_2",
            }
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 5 compatibility rejection checker")
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "docs" / "payload_v2" / "evidence" / "gate5_compatibility_rejection_report.json"),
    )
    args = parser.parse_args()

    compose = _compose_fixture(with_npc=True)
    payload_v2 = build_plugin_payload_v2(compose, player_id="gate5_runner", strict_mode=False)
    payload_v1 = build_plugin_payload_v1(_compose_fixture(with_npc=False), player_id="gate5_runner")

    exec_reject = execute_payload_v1(payload_v2)
    replay_reject = replay_payload_v1(payload_v2)
    exec_v1_ok = execute_payload_v1(payload_v1)

    checks = [
        {
            "name": "v2_to_executor_v1_reject",
            "pass": exec_reject.get("status") == "REJECTED" and exec_reject.get("failure_code") == "UNSUPPORTED_PAYLOAD_VERSION",
            "result": exec_reject,
        },
        {
            "name": "v2_to_replay_v1_reject",
            "pass": replay_reject.get("status") == "REJECTED" and replay_reject.get("failure_code") == "UNSUPPORTED_REPLAY_VERSION",
            "result": replay_reject,
        },
        {
            "name": "v1_to_executor_v1_pass",
            "pass": exec_v1_ok.get("status") == "SUCCESS" and exec_v1_ok.get("failure_code") == "NONE",
            "result": {
                "status": exec_v1_ok.get("status"),
                "failure_code": exec_v1_ok.get("failure_code"),
                "executed_commands": exec_v1_ok.get("executed_commands"),
                "world_state_hash": exec_v1_ok.get("world_state_hash"),
            },
        },
    ]

    overall_pass = all(bool(item.get("pass")) for item in checks)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "Gate 5 — Compatibility Rejection",
        "overall_pass": overall_pass,
        "checks": checks,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "overall_pass": overall_pass,
        "output": str(output_path),
        "checks": [{"name": item.get("name"), "pass": item.get("pass")} for item in checks],
    }, ensure_ascii=False))

    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
