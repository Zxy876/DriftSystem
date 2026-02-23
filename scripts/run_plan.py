#!/usr/bin/env python3
"""Minimal CLI to execute a saved CreationPlan JSON without a live API server.

Usage:
    python scripts/run_plan.py path/to/plan.json [options]

Options:
    --dry-run           Validate and print commands; do not send to RCON.
    --rcon-host HOST    RCON server hostname (default: 127.0.0.1).
    --rcon-port PORT    RCON port (default: 25575).
    --rcon-password PW  RCON password (required for live execution).
    --scene-id ID       Scene identifier written to the build timeline log.

Example:
    python scripts/run_plan.py backend/data/scenes/example_plan.json --dry-run
    python scripts/run_plan.py backend/data/scenes/example_plan.json \\
        --rcon-host 127.0.0.1 --rcon-port 25575 --rcon-password secret
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from the repository root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.creation.transformer import (
    CreationPlan,
    CreationPlanMaterial,
    CreationPatchTemplate,
)
from app.core.creation.validation import PatchTemplateValidationResult
from app.core.world.patch_executor import PatchExecutor
from app.core.world.patch_transaction import PatchTransactionLog
from app.core.world.plan_executor import PlanExecutor
from app.core.world.world_listener import WorldBuildEventLog
from app.core.minecraft.rcon_client import RconClient


def load_plan(path: Path) -> CreationPlan:
    """Deserialise a CreationPlan from its JSON representation."""
    payload = json.loads(path.read_text("utf-8"))

    materials = [
        CreationPlanMaterial(
            token=m["token"],
            resource_id=m.get("resource_id"),
            label=m.get("label"),
            status=m["status"],
            confidence=float(m.get("confidence", 0.0)),
            quantity=int(m.get("quantity", 0)),
            tags=list(m.get("tags", [])),
        )
        for m in payload.get("materials", [])
    ]

    patch_templates = []
    for t in payload.get("patch_templates", []):
        validation_data = t.get("validation") or {}
        validation = PatchTemplateValidationResult(
            errors=list(validation_data.get("errors", [])),
            warnings=list(validation_data.get("warnings", [])),
            execution_tier=str(validation_data.get("execution_tier", "needs_confirm")),
            missing_fields=list(validation_data.get("missing_fields", [])),
            unsafe_placeholders=list(validation_data.get("unsafe_placeholders", [])),
        )
        patch_templates.append(
            CreationPatchTemplate(
                step_id=t["step_id"],
                template_id=t["template_id"],
                status=t.get("status", "draft"),
                summary=t.get("summary", ""),
                step_type=t.get("step_type", "manual_review"),
                world_patch=dict(t.get("world_patch") or {}),
                mod_hooks=list(t.get("mod_hooks") or []),
                requires_player_pose=bool(t.get("requires_player_pose", False)),
                notes=list(t.get("notes") or []),
                tags=list(t.get("tags") or []),
                validation=validation,
            )
        )

    return CreationPlan(
        action=payload.get("action"),
        materials=materials,
        confidence=float(payload.get("confidence", 0.0)),
        summary=payload.get("summary", ""),
        patch_templates=patch_templates,
        notes=list(payload.get("notes") or []),
        execution_tier=str(payload.get("execution_tier", "needs_confirm")),
    )


class _PrintRunner:
    """Prints commands instead of sending them; used for --dry-run."""

    def run(self, commands):
        for cmd in commands:
            print(f"  [DRY-RUN] {cmd}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute a saved CreationPlan JSON against a Minecraft server via RCON."
    )
    parser.add_argument("plan", help="Path to a CreationPlan JSON file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print commands; skip RCON dispatch.",
    )
    parser.add_argument("--rcon-host", default="127.0.0.1", metavar="HOST")
    parser.add_argument("--rcon-port", type=int, default=25575, metavar="PORT")
    parser.add_argument("--rcon-password", default="", metavar="PASSWORD")
    parser.add_argument(
        "--scene-id",
        default="default",
        metavar="ID",
        help="Scene identifier recorded in the build timeline log.",
    )
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"ERROR: plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    plan = load_plan(plan_path)
    print(
        f"Loaded plan: {plan.summary!r} | tier={plan.execution_tier} | "
        f"templates={len(plan.patch_templates)}"
    )

    # Dry-run: validate only, no RCON.
    patch_executor = PatchExecutor()
    if args.dry_run:
        result = patch_executor.dry_run(plan)
        print(
            f"Dry-run result: executed={len(result.executed)} "
            f"skipped={len(result.skipped)} errors={len(result.errors)}"
        )
        for entry in result.executed:
            print(f"  [WOULD EXECUTE] {entry.template_id}")
            for cmd in entry.commands:
                print(f"    {cmd}")
        for skipped in result.skipped:
            print(f"  [SKIP] {skipped.template_id}: {skipped.reason}")
        for error in result.errors:
            print(f"  [ERROR] {error}", file=sys.stderr)
        return

    # Live execution via RCON.
    if not args.rcon_password:
        print(
            "WARNING: --rcon-password not supplied; commands will be printed only.",
            file=sys.stderr,
        )
        runner: object = _PrintRunner()
    else:
        runner = RconClient(
            host=args.rcon_host,
            port=args.rcon_port,
            password=args.rcon_password,
        )

    event_log = WorldBuildEventLog()
    plan_executor = PlanExecutor(patch_executor=patch_executor, command_runner=runner)
    report = plan_executor.auto_execute(plan)

    # Record build events to the structured timeline.
    if report.patch_id:
        for res in report.execution_results:
            if res.commands:
                event_log.record_commands(
                    res.commands,
                    plan_id=report.patch_id,
                    step_id=res.step_id,
                    scene_id=args.scene_id,
                )

    print(f"Execution complete: patch_id={report.patch_id}")
    for res in report.execution_results:
        print(f"  [{res.status.upper()}] {res.template_id}")

    if report.errors:
        for err in report.errors:
            print(f"  ERROR: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
