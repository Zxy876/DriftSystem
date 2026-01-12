#!/usr/bin/env python3
"""Regression harness for the legacy CityPhone API contract.

Iteration 0 要求之一是“编写回归脚本”，本脚本通过直接实例化
`IdealCityPipeline` 检查 CityPhone state/action 的关键结构，避免
在后续改造前无意破坏既有客户端依赖。

用法：
    python scripts/verify_cityphone_contract.py [--output SNAPSHOT_PATH]

- 默认读取 `IDEAL_CITY_DATA_ROOT` 环境变量；若缺失，退回到
  `backend/data/ideal_city`。
- 输出包含两部分：
  1. `state_snapshot`：`GET /ideal-city/cityphone/state/{player}` 结果。
  2. `action_snapshot`：提交未知动作时的响应。
- 可通过 `--output` 将快照写入 JSON 文件（包含 state/action 两个顶层字段）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


SCRIPT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.ideal_city.pipeline import CityPhoneAction, IdealCityPipeline


REQUIRED_STATE_KEYS = {
    "city_interpretation",
    "unknowns",
    "history_entries",
    "narrative",
    "exhibit_mode",
}

FORBIDDEN_STATE_KEYS = {
    "player_id",
    "scenario_id",
    "phase",
    "appendix",
    "plan",
    "resources",
    "location",
    "vision",
    "technology_status",
    "ready_for_build",
    "available",
    "pending",
    "status",
}

REQUIRED_NARRATIVE_KEYS = {"mode", "sections"}


class ContractViolation(RuntimeError):
    """Raised when the observed payload diverges from the frozen contract."""


def _resolve_data_root() -> Path:
    override = os.getenv("IDEAL_CITY_DATA_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data" / "ideal_city"


def _dump(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return JSON-serialisable dict (ensure_ascii preserved upstream)."""

    return json.loads(json.dumps(payload, ensure_ascii=False))


def _verify_state_payload(state: Dict[str, Any]) -> None:
    missing = REQUIRED_STATE_KEYS - set(state)
    if missing:
        raise ContractViolation(f"state payload missing keys: {sorted(missing)}")

    forbidden = FORBIDDEN_STATE_KEYS.intersection(state)
    if forbidden:
        raise ContractViolation(f"state payload exposes forbidden keys: {sorted(forbidden)}")

    narrative = state.get("narrative")
    if not isinstance(narrative, dict):
        raise ContractViolation("state['narrative'] must be an object")
    missing_narrative = REQUIRED_NARRATIVE_KEYS - set(narrative)
    if missing_narrative:
        raise ContractViolation(
            f"state['narrative'] missing keys: {sorted(missing_narrative)}"
        )
    sections = narrative.get("sections")
    if not isinstance(sections, list):
        raise ContractViolation("state['narrative']['sections'] must be an array")
    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ContractViolation(f"narrative section {idx} must be an object")
        for key in ("slot", "title", "body"):
            if key not in section:
                raise ContractViolation(
                    f"narrative section {idx} missing '{key}'"
                )
        if not isinstance(section["body"], list):
            raise ContractViolation(
                f"narrative section {idx} 'body' must be an array"
            )

    exhibit_mode = state.get("exhibit_mode")
    if not isinstance(exhibit_mode, dict):
        raise ContractViolation("state['exhibit_mode'] must be an object")
    allowed_exhibit_keys = {"label", "description"}
    extra_exhibit = set(exhibit_mode) - allowed_exhibit_keys
    if extra_exhibit:
        raise ContractViolation(
            f"state['exhibit_mode'] exposes unsupported keys: {sorted(extra_exhibit)}"
        )
    if not isinstance(exhibit_mode.get("description", []), list):
        raise ContractViolation(
            "state['exhibit_mode']['description'] must be an array"
        )


def run_contract_probe(output: Path | None = None) -> None:
    data_root = _resolve_data_root()
    # 初始化时显式设定数据根目录，避免脚本运行环境缺省变量导致读取失败。
    os.environ.setdefault("IDEAL_CITY_DATA_ROOT", str(data_root))
    pipeline = IdealCityPipeline()

    state = pipeline.cityphone_state("contract_probe", "default").model_dump(mode="json")
    _verify_state_payload(state)

    action = CityPhoneAction(
        player_id="contract_probe",
        action="pose_sync",
        payload={"x": 0, "y": 64, "z": 0, "world": "world"},
        scenario_id="default",
    )
    result = pipeline.handle_cityphone_action(action).model_dump(mode="json")
    if "state" not in result:
        raise ContractViolation("action response missing 'state'")
    _verify_state_payload(result["state"])

    snapshot = {
        "state_snapshot": _dump(state),
        "action_snapshot": _dump(result),
    }

    json_output = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_output, encoding="utf-8")
        print(f"[contract] snapshot written to {output}")
    else:
        print(json_output)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the JSON snapshot (state + action).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        run_contract_probe(args.output)
    except ContractViolation as exc:
        print(f"[contract] violation detected: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
