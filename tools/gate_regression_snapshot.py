from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = REPO_ROOT / "docs" / "payload_v2" / "evidence"
SNAPSHOT_ROOT = EVIDENCE_ROOT / "gate_regression"

GATE_REPORTS = [
    "gate2_replay_report.json",
    "gate2b_execution_replay_report.json",
    "gate3_hash_consistency_report.json",
    "gate4_strict_integrity_report.json",
    "gate5_compatibility_rejection_report.json",
    "gate6_rule_immutability_report.json",
    "gate7_rollback_safety_report.json",
]

BASELINE_TESTS = [
    "tests/test_phase4_world_patch_module_d.py",
    "tests/test_phase4_resource_mapping_module_b.py",
    "tests/test_phase4_npc_state_module_a.py",
    "tests/test_phase4_event_runtime_module_c.py",
    "tests/test_trng_transaction_shell.py",
]


def sha256_and_size(path: Path) -> tuple[str, int]:
    payload = path.read_bytes()
    return hashlib.sha256(payload).hexdigest(), len(payload)


def run_baseline(snapshot_dir: Path) -> tuple[int, str]:
    output_path = snapshot_dir / "phase4_baseline_test_output.txt"
    cmd = ["python3", "-m", "pytest", "-q", *BASELINE_TESTS]
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    content = (completed.stdout or "") + (completed.stderr or "")
    output_path.write_text(content, encoding="utf-8")
    return completed.returncode, str(output_path.relative_to(REPO_ROOT))


def copy_gate_reports(snapshot_dir: Path) -> dict[str, bool]:
    copied: dict[str, bool] = {}
    for name in GATE_REPORTS:
        source = EVIDENCE_ROOT / name
        target = snapshot_dir / name
        if source.exists():
            shutil.copy2(source, target)
            copied[name] = True
        else:
            copied[name] = False
    return copied


def collect_manifest_entries(snapshot_dir: Path) -> dict[str, dict[str, int | str]]:
    entries: dict[str, dict[str, int | str]] = {}
    for path in sorted(snapshot_dir.glob("*")):
        if not path.is_file():
            continue
        digest, size = sha256_and_size(path)
        rel = str(path.relative_to(REPO_ROOT))
        entries[rel] = {"sha256": digest, "bytes": size}
    return entries


def load_gate_status(snapshot_dir: Path) -> dict[str, bool | None]:
    status: dict[str, bool | None] = {}
    for report in GATE_REPORTS:
        path = snapshot_dir / report
        if not path.exists():
            status[report] = None
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            status[report] = bool(data.get("overall_pass"))
        except Exception:
            status[report] = None
    return status


def write_snapshot_markdown(
    snapshot_dir: Path,
    *,
    snapshot_id: str,
    commit_hash: str,
    baseline_return_code: int,
    gate_status: dict[str, bool | None],
) -> None:
    md_path = snapshot_dir / "GATE_REGRESSION_EVIDENCE_SNAPSHOT.md"
    gate_lines = []
    overall_pass = True
    for report in GATE_REPORTS:
        value = gate_status.get(report)
        if value is True:
            gate_lines.append(f"- {report}: PASS")
        elif value is False:
            gate_lines.append(f"- {report}: FAIL")
            overall_pass = False
        else:
            gate_lines.append(f"- {report}: MISSING")
            overall_pass = False

    if baseline_return_code != 0:
        overall_pass = False

    lines = [
        f"# Gate Regression Evidence Snapshot ({snapshot_id})",
        "",
        "## Snapshot Intent",
        "- Freeze the latest gate regression evidence after full rerun.",
        "- Keep a timestamped, hash-bound audit package before Phase5 design stage.",
        "",
        "## Anchors",
        f"- generated_at_utc: `{datetime.now(timezone.utc).isoformat()}`",
        f"- commit_hash: `{commit_hash}`",
        f"- snapshot_id: `{snapshot_id}`",
        "",
        "## Baseline Regression",
        f"- command: `python3 -m pytest -q {' '.join(BASELINE_TESTS)}`",
        f"- return_code: `{baseline_return_code}`",
        "- output: `phase4_baseline_test_output.txt`",
        "",
        "## Gate Results",
        *gate_lines,
        "",
        "## Overall",
        f"- overall_pass: `{str(overall_pass).lower()}`",
        "",
        "## Included Files",
        "- `phase4_baseline_test_output.txt`",
        *[f"- `{name}`" for name in GATE_REPORTS],
        "- `artifact_manifest.json`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create timestamped gate regression evidence snapshot")
    parser.add_argument("--snapshot-id", type=str, default="")
    args = parser.parse_args()

    snapshot_id = args.snapshot_id or datetime.now(timezone.utc).strftime("snapshot_%Y%m%dT%H%M%SZ")
    snapshot_dir = SNAPSHOT_ROOT / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    commit_hash = subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True).strip()

    baseline_code, baseline_output_rel = run_baseline(snapshot_dir)
    copied = copy_gate_reports(snapshot_dir)
    gate_status = load_gate_status(snapshot_dir)

    write_snapshot_markdown(
        snapshot_dir,
        snapshot_id=snapshot_id,
        commit_hash=commit_hash,
        baseline_return_code=baseline_code,
        gate_status=gate_status,
    )

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": snapshot_id,
        "commit_hash": commit_hash,
        "baseline": {
            "return_code": baseline_code,
            "output": baseline_output_rel,
        },
        "gate_reports_copied": copied,
        "gate_status": gate_status,
        "artifacts": collect_manifest_entries(snapshot_dir),
    }
    manifest_path = snapshot_dir / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    overall_pass = baseline_code == 0 and all(value is True for value in gate_status.values())
    print(
        json.dumps(
            {
                "snapshot_dir": str(snapshot_dir.relative_to(REPO_ROOT)),
                "baseline_return_code": baseline_code,
                "overall_pass": overall_pass,
                "manifest": str(manifest_path.relative_to(REPO_ROOT)),
            },
            ensure_ascii=False,
        )
    )
    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())