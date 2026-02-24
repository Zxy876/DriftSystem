#!/usr/bin/env python3
"""
生成 safe_auto 资源清单，作为语义覆盖率的权威分母。

数据来源：backend/data/transformer/resource_catalog.json
策略：
- 仅选择 resource_id 以 minecraft: 开头的条目
- 排除附带 commands 的条目（避免需要执行的资源）
- 结果写入 backend/tests/fixtures/safe_auto_resources.yaml
"""

from __future__ import annotations

import json
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = BACKEND_ROOT / "data" / "transformer" / "resource_catalog.json"
OUTPUT_PATH = BACKEND_ROOT / "tests" / "fixtures" / "safe_auto_resources.yaml"


def load_catalog() -> dict:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("resource_catalog_format_invalid")
    return payload


def extract_safe_auto_entries(payload: dict) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for resource in payload.get("resources", []) or []:
        if not isinstance(resource, dict):
            continue
        resource_id = str(resource.get("resource_id") or "").strip()
        if not resource_id.startswith("minecraft:"):
            continue
        if resource.get("commands"):
            # 带命令的条目需要人工确认，不纳入 safe_auto 分母
            continue
        display_name = str(resource.get("label") or resource.get("display_name") or "").strip()
        entries.append((resource_id, display_name))
    entries.sort(key=lambda item: item[0])
    return entries


def dump_yaml(entries: list[tuple[str, str]]) -> str:
    lines: list[str] = [
        "# DriftSystem v1.18 safe_auto resources snapshot",
        "# Generated from data/transformer/resource_catalog.json",
        f"# Total resources: {len(entries)}",
        "safe_auto_resources:",
    ]
    for resource_id, display_name in entries:
        lines.append(f"  - resource_id: {resource_id}")
        if display_name:
            lines.append(f"    display_name: {display_name}")
        else:
            lines.append("    display_name:")
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = load_catalog()
    entries = extract_safe_auto_entries(payload)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(dump_yaml(entries), encoding="utf-8")
    print(f"wrote {len(entries)} safe_auto resources to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
