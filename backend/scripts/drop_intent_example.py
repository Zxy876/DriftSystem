#!/usr/bin/env python3
"""Utility script for publishing a sample Manifestation Intent payload.

The tool writes an envelope JSON file into the protocol delivery directory
(`city-intents/pending/`) using the same machinery as the production pipeline.
It helps Forge developers validate their consumer implementation without
waiting for a full adjudication flow.
"""

from __future__ import annotations

import argparse
import os
from datetime import timedelta
from pathlib import Path
from typing import Iterable, List, Sequence

from app.core.ideal_city.manifestation_intent import ManifestationIntent
from app.core.ideal_city.manifestation_writer import ManifestationIntentWriter

_DEFAULT_PROTOCOL_SUBDIR = Path("backend") / "data" / "ideal_city" / "protocol"
_PLACEHOLDER_PLAYER_ID = "00000000-0000-0000-0000-000000000000"


def _default_protocol_root() -> Path:
    override = os.getenv("IDEAL_CITY_PROTOCOL_ROOT")
    if override:
        return Path(override).expanduser()
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / _DEFAULT_PROTOCOL_SUBDIR).resolve()


def _collect_multi_value(values: Sequence[str] | None) -> List[str]:
    payload: List[str] = []
    if not values:
        return payload
    for entry in values:
        if not entry:
            continue
        payload.append(entry.strip())
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish a sample Manifestation Intent envelope")
    parser.add_argument(
        "--player-id",
        default=_PLACEHOLDER_PLAYER_ID,
        help="Target player UUID (default: placeholder UUID for dry runs)",
    )
    parser.add_argument(
        "--scenario-id",
        default="default",
        help="Scenario identifier associated with the intent",
    )
    parser.add_argument(
        "--scenario-version",
        default=None,
        help="Optional scenario version string written into the intent payload",
    )
    parser.add_argument(
        "--stage",
        type=int,
        default=1,
        help="Allowed stage value announced to Forge (default: 1)",
    )
    parser.add_argument(
        "--constraint",
        action="append",
        dest="constraints",
        help="Constraint entry to embed in the payload; may be supplied multiple times",
    )
    parser.add_argument(
        "--note",
        action="append",
        dest="context_notes",
        help="Context note entry to embed in the payload; may be supplied multiple times",
    )
    parser.add_argument(
        "--ttl-hours",
        type=int,
        default=24,
        help="Validity window in hours before the intent expires (default: 24)",
    )
    parser.add_argument(
        "--spec-id",
        default=None,
        help="Optional source DeviceSpec ID for traceability",
    )
    parser.add_argument(
        "--protocol-root",
        default=None,
        help="Override the protocol root directory; defaults to IDEAL_CITY_PROTOCOL_ROOT or repo path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Construct payload without writing to disk; prints JSON to stdout",
    )
    return parser


def _resolve_protocol_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return _default_protocol_root()


def _ensure_constraints(base: Iterable[str]) -> List[str]:
    constraints = list(base)
    if not constraints:
        constraints.append("no_stage_skip")
    return constraints


def publish_sample_intent(args: argparse.Namespace) -> ManifestationIntent:
    constraints = _ensure_constraints(_collect_multi_value(args.constraints))
    notes = _collect_multi_value(args.context_notes)
    ttl = timedelta(hours=max(args.ttl_hours, 1))

    intent = ManifestationIntent.create(
        scenario_id=args.scenario_id,
        scenario_version=args.scenario_version,
        allowed_stage=args.stage,
        constraints=constraints,
        context_notes=notes or ["紫水晶基础实验获准进行"],
        ttl=ttl,
    )

    if args.dry_run:
        return intent

    protocol_root = _resolve_protocol_root(args.protocol_root)
    writer = ManifestationIntentWriter(protocol_root)
    writer.write_intent(intent, player_id=args.player_id, spec_id=args.spec_id)
    return intent


def format_summary(intent: ManifestationIntent, *, player_id: str, protocol_root: Path | None) -> str:
    lines = [
        "Published Manifestation Intent:",
        f"  intent_id      : {intent.intent_id}",
        f"  scenario_id    : {intent.scenario_id}",
        f"  allowed_stage  : {intent.allowed_stage}",
        f"  expires_at     : {intent.expires_at.isoformat()}",
        f"  player_id      : {player_id}",
    ]
    if protocol_root is not None:
        lines.append(f"  protocol_root  : {protocol_root}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.stage < 0:
        parser.error("--stage must be non-negative")
    if not args.player_id:
        parser.error("--player-id must not be empty")
    if args.protocol_root is not None and not args.protocol_root.strip():
        parser.error("--protocol-root must not be empty when provided")

    intent = publish_sample_intent(args)

    if args.dry_run:
        import json

        print(json.dumps({"intent": intent.model_dump(mode="json")}, ensure_ascii=False, indent=2))
        return 0

    summary = format_summary(
        intent,
        player_id=args.player_id,
        protocol_root=_resolve_protocol_root(args.protocol_root),
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
