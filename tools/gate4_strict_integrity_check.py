from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.main import app
from app.api.story_api import DATA_DIR


STRICT_PROMPT = "在湖边制造一个神秘雾气与低沉音乐的场景"


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


def check_strict_debug() -> dict:
    level_id = f"flagship_gate4_debug_{uuid.uuid4().hex[:8]}"
    target = _level_file(level_id)
    if target.exists():
        target.unlink()

    prior = _set_env(
        {
            "DRIFT_USE_PAYLOAD_V1": "false",
            "DRIFT_USE_PAYLOAD_V2": "true",
            "DRIFT_V2_STRICT_MODE": "true",
            "DRIFT_DEBUG_TRACE": "true",
        }
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/story/inject",
                json={
                    "level_id": level_id,
                    "title": "gate4 strict debug",
                    "text": STRICT_PROMPT,
                    "player_id": "gate4_debug_runner",
                },
            )

        body = response.json()
        pass_flag = (
            response.status_code == 422
            and "EXEC_CAPABILITY_GAP" in str(body.get("detail") or "")
            and "final_commands_hash_v2" not in body
            and "hash" not in body
            and isinstance(body.get("decision_trace"), dict)
            and isinstance(body.get("rule_version"), str)
            and isinstance(body.get("engine_version"), str)
            and not target.exists()
        )

        return {
            "name": "strict_debug_zero_side_effect",
            "pass": pass_flag,
            "status_code": response.status_code,
            "target_file_exists": target.exists(),
            "has_trace": isinstance(body.get("decision_trace"), dict),
            "has_rule_version": isinstance(body.get("rule_version"), str),
            "has_engine_version": isinstance(body.get("engine_version"), str),
        }
    finally:
        _restore_env(prior)
        if target.exists():
            target.unlink()


def check_strict_no_debug() -> dict:
    level_id = f"flagship_gate4_nodbg_{uuid.uuid4().hex[:8]}"
    target = _level_file(level_id)
    if target.exists():
        target.unlink()

    prior = _set_env(
        {
            "DRIFT_USE_PAYLOAD_V1": "false",
            "DRIFT_USE_PAYLOAD_V2": "true",
            "DRIFT_V2_STRICT_MODE": "true",
            "DRIFT_DEBUG_TRACE": "false",
        }
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/story/inject",
                json={
                    "level_id": level_id,
                    "title": "gate4 strict no debug",
                    "text": STRICT_PROMPT,
                    "player_id": "gate4_nodbg_runner",
                },
            )

        body = response.json()
        forbidden = {
            "mapping_status",
            "mapping_failure_code",
            "degrade_reason",
            "lost_semantics",
            "rule_version",
            "engine_version",
            "decision_trace",
            "compose_path",
        }
        pass_flag = response.status_code == 422 and not any(key in body for key in forbidden) and not target.exists()

        return {
            "name": "strict_nodbg_hidden_fields",
            "pass": pass_flag,
            "status_code": response.status_code,
            "target_file_exists": target.exists(),
        }
    finally:
        _restore_env(prior)
        if target.exists():
            target.unlink()


def check_default_vs_strict_isolation() -> dict:
    default_level_id = f"flagship_gate4_default_{uuid.uuid4().hex[:8]}"
    strict_level_id = f"flagship_gate4_strict_{uuid.uuid4().hex[:8]}"
    default_target = _level_file(default_level_id)
    strict_target = _level_file(strict_level_id)
    for path in (default_target, strict_target):
        if path.exists():
            path.unlink()

    prior = _set_env(
        {
            "DRIFT_USE_PAYLOAD_V1": "false",
            "DRIFT_USE_PAYLOAD_V2": "true",
            "DRIFT_DEBUG_TRACE": "true",
        }
    )

    try:
        os.environ["DRIFT_V2_STRICT_MODE"] = "false"
        with TestClient(app) as client:
            default_response = client.post(
                "/story/inject",
                json={
                    "level_id": default_level_id,
                    "title": "gate4 default",
                    "text": STRICT_PROMPT,
                    "player_id": "gate4_default_runner",
                },
            )

        os.environ["DRIFT_V2_STRICT_MODE"] = "true"
        with TestClient(app) as client:
            strict_response = client.post(
                "/story/inject",
                json={
                    "level_id": strict_level_id,
                    "title": "gate4 strict",
                    "text": STRICT_PROMPT,
                    "player_id": "gate4_strict_runner",
                },
            )

        strict_body = strict_response.json()
        pass_flag = (
            default_response.status_code == 200
            and strict_response.status_code == 422
            and default_target.exists()
            and not strict_target.exists()
            and "final_commands_hash_v2" not in strict_body
        )

        return {
            "name": "default_not_pollute_strict",
            "pass": pass_flag,
            "default_status_code": default_response.status_code,
            "strict_status_code": strict_response.status_code,
            "default_target_exists": default_target.exists(),
            "strict_target_exists": strict_target.exists(),
        }
    finally:
        _restore_env(prior)
        for path in (default_target, strict_target):
            if path.exists():
                path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 4 strict reject integrity checker")
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "docs" / "payload_v2" / "evidence" / "gate4_strict_integrity_report.json"),
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    checks = [
        check_strict_debug(),
        check_strict_no_debug(),
        check_default_vs_strict_isolation(),
    ]

    overall_pass = all(bool(item.get("pass")) for item in checks)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "Gate 4 — Strict Reject Integrity",
        "overall_pass": overall_pass,
        "checks": checks,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "overall_pass": overall_pass,
        "output": str(output_path),
        "checks": [{"name": item.get("name"), "pass": item.get("pass")} for item in checks],
    }, ensure_ascii=False))

    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
