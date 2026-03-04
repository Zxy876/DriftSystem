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

from app.core.mapping.projection_rule_registry import DEFAULT_RULE_VERSION, PROJECTION_RULE_REGISTRY
from app.core.mapping.rule_immutability_guard import evaluate_rule_immutability


FREEZE_SNAPSHOT_PATH = BACKEND_ROOT / "app" / "core" / "mapping" / "projection_rule_registry_freeze.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 6 rule immutability checker")
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "docs" / "payload_v2" / "evidence" / "gate6_rule_immutability_report.json"),
    )
    parser.add_argument(
        "--snapshot",
        type=str,
        default=str(FREEZE_SNAPSHOT_PATH),
    )
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists():
        report = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "gate": "Gate 6 — Projection Rule Immutability",
            "overall_pass": False,
            "error": "FREEZE_SNAPSHOT_NOT_FOUND",
            "snapshot": str(snapshot_path),
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"overall_pass": False, "output": str(output_path), "error": "FREEZE_SNAPSHOT_NOT_FOUND"}, ensure_ascii=False))
        return 2

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    result = evaluate_rule_immutability(
        default_rule_version=DEFAULT_RULE_VERSION,
        registry=PROJECTION_RULE_REGISTRY,
        freeze_snapshot=snapshot,
    )

    overall_pass = result.get("status") == "PASS"
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "Gate 6 — Projection Rule Immutability",
        "overall_pass": overall_pass,
        "snapshot": str(snapshot_path),
        "default_rule_version": DEFAULT_RULE_VERSION,
        "result": result,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "overall_pass": overall_pass,
        "output": str(output_path),
        "default_rule_version": DEFAULT_RULE_VERSION,
        "failure_codes": result.get("failure_codes") or [],
    }, ensure_ascii=False))

    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
