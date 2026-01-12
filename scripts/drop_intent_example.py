#!/usr/bin/env python3
"""Emit a sample Manifestation Intent into city-intents/pending for Forge testing."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path


def emit_intent(protocol_root: Path, *, scenario_id: str, stage: int, player_id: str) -> Path:
    pending_dir = protocol_root / "city-intents" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    intent_id = f"EXAMPLE_STAGE_{stage}_{timestamp}"
    payload = {
        "intent_id": intent_id,
        "intent_kind": "CRYSTAL_TECH_STAGE_UNLOCK",
        "schema_version": "0.1.0",
        "scenario_id": scenario_id,
        "allowed_stage": stage,
        "confidence_level": "research_validated",
        "issued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp)),
        "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp + 24 * 3600)),
        "notes": ["联调用示例意图"],
        "metadata": {"source_spec_id": "EXAMPLE_SPEC"},
        "signature": "ideal-city::example",
    }

    envelope = {
        "player_id": player_id,
        "intent": payload,
    }

    fd, temp_path_str = tempfile.mkstemp(prefix=".intent_", suffix=".json", dir=pending_dir)
    temp_path = Path(temp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(envelope, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        final_path = pending_dir / f"{intent_id}.json"
        os.replace(temp_path, final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return final_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a sample Manifestation Intent for Forge testing")
    parser.add_argument(
        "--protocol-root",
        default=os.environ.get("IDEAL_CITY_PROTOCOL_ROOT", "."),
        help="Root directory containing city-intents. Defaults to IDEAL_CITY_PROTOCOL_ROOT or current directory.",
    )
    parser.add_argument("--scenario", default="default", help="Scenario identifier to embed in the intent")
    parser.add_argument("--stage", type=int, default=1, help="Stage allowance to grant in the intent")
    parser.add_argument(
        "--player-id",
        default="00000000-0000-0000-0000-000000000000",
        help="Player UUID authorized for this intent; placeholder UUID accepted for testing",
    )
    args = parser.parse_args()

    protocol_root = Path(args.protocol_root).resolve()
    final_path = emit_intent(
        protocol_root,
        scenario_id=args.scenario,
        stage=args.stage,
        player_id=args.player_id,
    )
    print(f"Intent written to: {final_path}")


if __name__ == "__main__":
    main()
