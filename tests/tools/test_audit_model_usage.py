"""Tests for audit_model_usage.py (Issue 6.2)."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT / "tools"
for path in (ROOT, TOOLS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from audit_model_usage import iter_logs, render_report


def test_iter_and_render(tmp_path: Path, monkeypatch):
    log_dir = tmp_path / "backend/logs/model_usage"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "usage.jsonl"
    log_file.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-01-22T10:00:00Z","model":"gpt-4o-mini","user":"u1","reason":"test","tokens":123}',
                '{"timestamp":"2026-01-21T10:00:00Z","model":"gpt-4o-mini","user":"u2","reason":"prev","tokens":200}',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("audit_model_usage.LOG_DIR", log_dir)

    entries_all = list(iter_logs())
    assert len(entries_all) == 2

    entries_filtered = list(iter_logs("2026-01-22"))
    assert len(entries_filtered) == 1

    report = render_report(entries_filtered)
    assert "总计：1" in report
    assert "u1" in report
