from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.main import app
from app.api.story_api import DATA_DIR
from app.core.executor.executor_v1 import execute_payload_v1
from app.core.executor.replay_v1 import replay_payload_v1


PROMPT = "平静夜晚的湖边，有一座7x5木屋，门朝南，开两扇窗"


def _level_file(level_id: str) -> Path:
    return Path(DATA_DIR) / f"{level_id}.json"


def _set_env(values: dict[str, str | None]) -> dict[str, str | None]:
    prior = {key: os.environ.get(key) for key in values.keys()}
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return prior


def _restore_env(prior: dict[str, str | None]) -> None:
    for key, value in prior.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def check_v2_off_routes_to_v1() -> dict:
    level_id = f"flagship_gate7_route_{uuid.uuid4().hex[:8]}"
    target = _level_file(level_id)
    if target.exists():
        target.unlink()

    prior = _set_env(
        {
            "DRIFT_USE_PAYLOAD_V1": "true",
            "DRIFT_USE_PAYLOAD_V2": "false",
            "DRIFT_USE_V2_MAPPER": "false",
            "DRIFT_V2_STRICT_MODE": "false",
            "DRIFT_DEBUG_TRACE": "false",
        }
    )

    try:
        with patch("app.api.story_api._build_payload_v2_for_inject", side_effect=AssertionError("v2 path should not be called")):
            with TestClient(app) as client:
                response = client.post(
                    "/story/inject",
                    json={
                        "level_id": level_id,
                        "title": "gate7 route",
                        "text": PROMPT,
                        "player_id": "gate7_route_runner",
                    },
                )

        body = response.json()
        pass_flag = (
            response.status_code == 200
            and body.get("version") == "plugin_payload_v1"
            and isinstance((body.get("hash") or {}).get("merged_blocks"), str)
            and "final_commands_hash_v2" not in body
            and target.exists()
        )

        return {
            "name": "v2_off_routes_to_payload_v1",
            "pass": pass_flag,
            "status_code": response.status_code,
            "payload_version": body.get("version"),
            "file_exists": target.exists(),
        }
    finally:
        _restore_env(prior)
        if target.exists():
            target.unlink()


def check_executor_and_replay_v1_pass() -> dict:
    level_id = f"flagship_gate7_exec_{uuid.uuid4().hex[:8]}"
    target = _level_file(level_id)
    if target.exists():
        target.unlink()

    prior = _set_env(
        {
            "DRIFT_USE_PAYLOAD_V1": "true",
            "DRIFT_USE_PAYLOAD_V2": "false",
            "DRIFT_USE_V2_MAPPER": "false",
            "DRIFT_V2_STRICT_MODE": "false",
            "DRIFT_DEBUG_TRACE": "false",
        }
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/story/inject",
                json={
                    "level_id": level_id,
                    "title": "gate7 exec replay",
                    "text": PROMPT,
                    "player_id": "gate7_exec_runner",
                },
            )

        body = response.json()
        exec_result = execute_payload_v1(body if isinstance(body, dict) else {})
        replay_result = replay_payload_v1(body if isinstance(body, dict) else {})

        pass_flag = (
            response.status_code == 200
            and body.get("version") == "plugin_payload_v1"
            and exec_result.get("status") == "SUCCESS"
            and replay_result.get("status") == "SUCCESS"
        )

        return {
            "name": "executor_replay_v1_pass_when_v2_off",
            "pass": pass_flag,
            "status_code": response.status_code,
            "payload_version": body.get("version"),
            "executor_status": exec_result.get("status"),
            "replay_status": replay_result.get("status"),
            "executor_failure_code": exec_result.get("failure_code"),
            "replay_failure_code": replay_result.get("failure_code"),
        }
    finally:
        _restore_env(prior)
        if target.exists():
            target.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 7 rollback safety checker")
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "docs" / "payload_v2" / "evidence" / "gate7_rollback_safety_report.json"),
    )
    args = parser.parse_args()

    checks = [
        check_v2_off_routes_to_v1(),
        check_executor_and_replay_v1_pass(),
    ]
    overall_pass = all(bool(item.get("pass")) for item in checks)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "Gate 7 — Rollback Safety",
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
