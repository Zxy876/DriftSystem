"""Audit tool for model usage logs (Issue 6.2).

读取 backend/logs/model_usage/*.jsonl，生成 Markdown 报告。默认日期为全部；支持 --date YYYY-MM-DD 过滤。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

LOG_DIR = Path("backend/logs/model_usage")


def iter_logs(date_filter: str | None = None) -> Iterable[dict]:
    if not LOG_DIR.exists():
        return []
    for path in sorted(LOG_DIR.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if date_filter:
                ts = obj.get("timestamp")
                if not ts or not ts.startswith(date_filter):
                    continue
            yield obj


def render_report(entries: List[dict]) -> str:
    if not entries:
        return "无记录"
    lines = ["# Model Usage Report", "", f"总计：{len(entries)} 条"]
    for item in entries:
        ts = item.get("timestamp", "?")
        model = item.get("model", "?")
        user = item.get("user", "?")
        reason = item.get("reason", "?")
        tokens = item.get("tokens", "?")
        lines.append(f"- {ts} | model={model} | user={user} | tokens={tokens} | reason={reason}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit model usage logs")
    parser.add_argument("--date", dest="date", help="YYYY-MM-DD", default=None)
    args = parser.parse_args()

    entries = list(iter_logs(args.date))
    report = render_report(entries)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
