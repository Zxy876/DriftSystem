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

from app.core.scene.scene_orchestrator_v2 import compose_scene_and_structure_v2


SCENARIOS = {
    "fog-only": "在湖边制造一个神秘雾气的场景",
    "npc-only": "在湖边放置一个静态守卫",
    "fog+npc": "在湖边制造一个神秘雾气并放置一个静态守卫",
}


def run_once(prompt: str) -> dict:
    result = compose_scene_and_structure_v2(prompt, strict_mode=False)
    mapping = result.get("mapping_result") if isinstance(result.get("mapping_result"), dict) else {}
    return {
        "status": result.get("status"),
        "failure_code": result.get("failure_code"),
        "mapping_status": mapping.get("status"),
        "mapping_failure_code": mapping.get("failure_code"),
        "lost_semantics": mapping.get("lost_semantics") or [],
        "merge_hash": result.get("merge_hash") or "",
        "scene_block_count": int(result.get("scene_block_count") or 0),
        "merged_block_count": int(result.get("merged_block_count") or 0),
    }


def run_scenario(name: str, prompt: str, rounds: int) -> dict:
    rows = [run_once(prompt) for _ in range(rounds)]

    hash_counter = Counter(item["merge_hash"] for item in rows)
    status_counter = Counter(item["status"] for item in rows)
    mapping_status_counter = Counter(item["mapping_status"] for item in rows)

    unique_hashes = sorted(hash_counter.keys())
    top_hash = unique_hashes[0] if len(unique_hashes) == 1 else (hash_counter.most_common(1)[0][0] if hash_counter else "")

    return {
        "scenario": name,
        "rounds": rounds,
        "status_counts": dict(status_counter),
        "mapping_status_counts": dict(mapping_status_counter),
        "unique_hashes": len(unique_hashes),
        "stable_hash": top_hash,
        "hash_counts": dict(hash_counter),
        "pass": len(unique_hashes) == 1,
        "sample": rows[0] if rows else {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 2 replay determinism dry-run checker")
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "docs" / "payload_v2" / "evidence" / "gate2_replay_report.json"),
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scenario_reports = [run_scenario(name, prompt, args.rounds) for name, prompt in SCENARIOS.items()]
    all_pass = all(item.get("pass") for item in scenario_reports)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "Gate 2 — Replay Determinism",
        "mode": "dry-run-projection-layer",
        "rounds_per_scenario": args.rounds,
        "overall_pass": all_pass,
        "scenarios": scenario_reports,
    }

    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "overall_pass": all_pass,
        "output": str(output_path),
        "scenarios": [{"scenario": s["scenario"], "unique_hashes": s["unique_hashes"], "pass": s["pass"]} for s in scenario_reports],
    }, ensure_ascii=False))
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
