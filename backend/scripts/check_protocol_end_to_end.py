"""End-to-end verifier for Ideal City ↔ CrystalTech protocol outputs.

This script automates a handshake smoke-test:
1. Optionally publish a sample Manifestation Intent into `city-intents/pending/`.
2. Wait for Forge to advance the stage and write back social feedback + technology status.
3. Validate that `cityphone/social-feed/` and `technology-status.json` follow the documented format.

Usage
-----
PYTHONPATH=backend python3 -m scripts.check_protocol_end_to_end \
    --protocol-root /path/to/protocol \
    --auto-drop-intent \
    --expected-stage 1 \
    --timeout 120

By default the script only inspects the directories and exits once both social
feed and technology status snapshots change. Use ``--auto-drop-intent`` to emit
an example intent before waiting for Forge outputs. The operator should trigger
stage advancement (e.g. via `/crystalintent grant`) after the script reports the
published intent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.ideal_city.manifestation_intent import ManifestationIntent
from app.core.ideal_city.manifestation_writer import ManifestationIntentWriter

ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


@dataclass
class SocialFeedState:
    event_count: int
    entry_ids: list[str]
    latest_timestamp: Optional[datetime]
    trust_index: Optional[float]
    raw_events: list[dict]

    def describe(self) -> str:
        if not self.event_count:
            return "no social events detected"
        if self.entry_ids:
            summary = f"{self.event_count} events (latest id: {self.entry_ids[-1]})"
        else:
            summary = f"{self.event_count} events"
        if self.trust_index is not None:
            summary += f", trust_index={self.trust_index:.3f}"
        if self.latest_timestamp is not None:
            summary += f", updated_at={self.latest_timestamp.isoformat()}"
        return summary


@dataclass
class TechnologyStatusState:
    stage_label: Optional[str]
    stage_level: Optional[int]
    stage_progress: Optional[float]
    updated_at: Optional[datetime]
    energy: dict[str, float]
    risk_count: int
    event_count: int
    raw_payload: dict[str, Any]

    def describe(self) -> str:
        pieces: list[str] = []
        if self.stage_level is not None:
            pieces.append(f"stage={self.stage_level}")
        if self.stage_label:
            pieces.append(self.stage_label)
        if self.stage_progress is not None:
            pieces.append(f"progress={self.stage_progress:.2f}")
        if self.updated_at is not None:
            pieces.append(f"updated={self.updated_at.isoformat()}")
        pieces.append(f"energy_keys={list(self.energy.keys()) or ['<none>']}")
        pieces.append(f"risks={self.risk_count}")
        pieces.append(f"events={self.event_count}")
        return ", ".join(pieces)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check protocol end-to-end outputs.")
    parser.add_argument(
        "--protocol-root",
        type=Path,
        default=Path(
            os.environ.get("CRYSTALTECH_PROTOCOL_ROOT")
            or os.environ.get("IDEAL_CITY_PROTOCOL_ROOT")
            or "backend/data/ideal_city/protocol"
        ),
        help="Path to the protocol root (defaults to env or backend/data/ideal_city/protocol).",
    )
    parser.add_argument("--player-id", default="00000000-0000-0000-0000-000000000000", help="Player UUID for the sample intent.")
    parser.add_argument("--scenario-id", default="default", help="Scenario id for the sample intent.")
    parser.add_argument("--scenario-version", default="2026.01", help="Scenario version tag for the sample intent.")
    parser.add_argument("--allowed-stage", type=int, default=1, help="Stage number the sample intent requests.")
    parser.add_argument("--timeout", type=int, default=120, help="Maximum seconds to wait for Forge outputs.")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between filesystem checks.")
    parser.add_argument("--expected-stage", type=int, default=None, help="Minimum stage level expected in technology-status.json.")
    parser.add_argument("--auto-drop-intent", action="store_true", help="Publish a sample intent before waiting for outputs.")
    parser.add_argument("--ttl-hours", type=float, default=6.0, help="Time-to-live (hours) for the sample Manifestation Intent.")
    return parser.parse_args(argv)


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in ISO_FORMATS:
            try:
                parsed = datetime.strptime(text, fmt)
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def load_json_file(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def load_social_feed_state(root: Path) -> SocialFeedState:
    events: list[dict] = []
    latest_timestamp: Optional[datetime] = None

    jsonl_path = root / "events.jsonl"
    if jsonl_path.exists():
        try:
            for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                events.append(payload)
        except OSError:
            pass

    for entry_path in sorted(root.glob("*.json")):
        if entry_path.name in {"metrics.json", "trust_index.json", "events.json"}:
            continue
        payload = load_json_file(entry_path)
        if isinstance(payload, dict):
            events.append(payload)

    entry_ids: list[str] = []
    for item in events:
        entry_id = str(item.get("entry_id") or item.get("id") or "").strip()
        if entry_id:
            entry_ids.append(entry_id)
        issued_at = parse_datetime(item.get("issued_at") or item.get("timestamp"))
        if issued_at is not None and (latest_timestamp is None or issued_at > latest_timestamp):
            latest_timestamp = issued_at

    metrics_payload = load_json_file(root / "metrics.json") or load_json_file(root / "trust_index.json")
    trust_index: Optional[float] = None
    if isinstance(metrics_payload, dict):
        trust_index_raw = metrics_payload.get("trust_index") or metrics_payload.get("value")
        if isinstance(trust_index_raw, (int, float)):
            trust_index = float(trust_index_raw)
        latest_candidate = parse_datetime(metrics_payload.get("updated_at"))
        if latest_candidate is not None and (latest_timestamp is None or latest_candidate > latest_timestamp):
            latest_timestamp = latest_candidate

    return SocialFeedState(
        event_count=len(events),
        entry_ids=entry_ids,
        latest_timestamp=latest_timestamp,
        trust_index=trust_index,
        raw_events=events,
    )


def load_technology_status_state(path: Path) -> TechnologyStatusState:
    payload = load_json_file(path)
    if not isinstance(payload, dict):
        return TechnologyStatusState(
            stage_label=None,
            stage_level=None,
            stage_progress=None,
            updated_at=None,
            energy={},
            risk_count=0,
            event_count=0,
            raw_payload={},
        )

    stage = payload.get("stage")
    stage_label: Optional[str] = None
    stage_level: Optional[int] = None
    stage_progress: Optional[float] = None
    if isinstance(stage, dict):
        label_raw = stage.get("label") or stage.get("name") or stage.get("description")
        stage_label = str(label_raw).strip() if isinstance(label_raw, str) else None
        level_raw = stage.get("level")
        if isinstance(level_raw, (int, float)):
            stage_level = int(level_raw)
        progress_raw = stage.get("progress")
        if isinstance(progress_raw, (int, float)):
            stage_progress = float(progress_raw)
    elif isinstance(stage, str) and stage.strip():
        stage_label = stage.strip()
    elif isinstance(stage, (int, float)):
        stage_level = int(stage)

    energy_payload = payload.get("energy")
    energy: dict[str, float] = {}
    if isinstance(energy_payload, dict):
        for key in ("generation", "consumption", "capacity", "storage", "buffer", "reserve"):
            value = energy_payload.get(key)
            if isinstance(value, (int, float)):
                energy[key] = float(value)

    risks_payload = payload.get("risks") or payload.get("risk_alerts") or []
    risk_count = len(risks_payload) if isinstance(risks_payload, list) else 0

    events_payload = payload.get("recent_events") or payload.get("events") or payload.get("event_log") or []
    event_count = len(events_payload) if isinstance(events_payload, list) else 0

    updated_at = parse_datetime(payload.get("updated_at"))
    if updated_at is None and isinstance(events_payload, list):
        for item in events_payload:
            if isinstance(item, dict):
                candidate = parse_datetime(item.get("occurred_at") or item.get("timestamp"))
                if candidate is not None and (updated_at is None or candidate > updated_at):
                    updated_at = candidate

    return TechnologyStatusState(
        stage_label=stage_label,
        stage_level=stage_level,
        stage_progress=stage_progress,
        updated_at=updated_at,
        energy=energy,
        risk_count=risk_count,
        event_count=event_count,
        raw_payload=payload,
    )


def publish_sample_intent(args: argparse.Namespace, protocol_root: Path) -> str:
    writer = ManifestationIntentWriter(protocol_root)
    ttl = timedelta(hours=args.ttl_hours)
    intent = ManifestationIntent.create(
        scenario_id=args.scenario_id,
        scenario_version=args.scenario_version,
        allowed_stage=args.allowed_stage,
        constraints=["no_stage_skip", "low_energy_only"],
        context_notes=[
            "端到端联调脚本生成：验证 Forge 阶段推进回写路径是否可用",
            "请在世界内执行阶段推进操作以消费该意图",
        ],
        ttl=ttl,
    )
    intent_path = writer.write_intent(intent, player_id=args.player_id)
    print(f"Published sample intent {intent.intent_id} to {intent_path}")
    print("Waiting for Forge to process the intent. Trigger stage advancement when ready.")
    return intent.intent_id


def wait_for_updates(
    protocol_root: Path,
    baseline_social: SocialFeedState,
    baseline_status: TechnologyStatusState,
    *,
    timeout: int,
    poll_interval: float,
    expected_stage: Optional[int],
) -> tuple[SocialFeedState, TechnologyStatusState]:
    social_dir = protocol_root / "cityphone" / "social-feed"
    status_path = protocol_root / "technology-status.json"

    deadline = time.time() + timeout
    last_report: float = 0.0

    while time.time() < deadline:
        social_state = load_social_feed_state(social_dir)
        status_state = load_technology_status_state(status_path)

        social_ready = social_state.event_count > baseline_social.event_count
        status_fresh = False
        if status_state.updated_at is None:
            status_fresh = baseline_status.updated_at is None and status_state.raw_payload != {}
        else:
            if baseline_status.updated_at is None:
                status_fresh = True
            else:
                status_fresh = status_state.updated_at > baseline_status.updated_at

        stage_ok = expected_stage is None or (
            (status_state.stage_level or 0) >= expected_stage
        )

        if social_ready and status_fresh and stage_ok:
            return social_state, status_state

        now = time.time()
        if now - last_report > max(poll_interval * 4, 15):
            print(
                "Waiting... social events=%d (baseline %d), status updated=%s"
                % (
                    social_state.event_count,
                    baseline_social.event_count,
                    status_state.updated_at.isoformat()
                    if status_state.updated_at is not None
                    else "<none>",
                )
            )
            last_report = now
        time.sleep(poll_interval)

    raise TimeoutError(
        "Timed out waiting for social feedback and technology status updates."
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    protocol_root = args.protocol_root.resolve()
    social_dir = protocol_root / "cityphone" / "social-feed"
    status_path = protocol_root / "technology-status.json"

    if not social_dir.exists():
        print(f"Creating social feed directory at {social_dir}")
        social_dir.mkdir(parents=True, exist_ok=True)
    if not status_path.parent.exists():
        status_path.parent.mkdir(parents=True, exist_ok=True)

    baseline_social = load_social_feed_state(social_dir)
    baseline_status = load_technology_status_state(status_path)

    print("Baseline social feed:", baseline_social.describe())
    print("Baseline technology status:", baseline_status.describe())

    if args.auto_drop_intent:
        publish_sample_intent(args, protocol_root)
    else:
        print("Auto intent drop disabled. Waiting for Forge outputs using existing intents.")

    try:
        social_state, status_state = wait_for_updates(
            protocol_root,
            baseline_social,
            baseline_status,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
            expected_stage=args.expected_stage,
        )
    except TimeoutError as exc:
        print(str(exc))
        return 1

    print("\n✅ Detected Forge outputs:")
    print("  • Social feed:", social_state.describe())
    if social_state.raw_events:
        latest_event = social_state.raw_events[-1]
        print("    Last event snippet:", json.dumps(latest_event, ensure_ascii=False))
    print("  • Technology status:", status_state.describe())
    print("    Raw payload:", json.dumps(status_state.raw_payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
