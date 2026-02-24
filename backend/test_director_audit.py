"""Tests for director audit logger (Issue 5.2)."""
from pathlib import Path
import json

from app.instrumentation.director_audit import log_decision, DIRECTOR_AUDIT_LOG


def test_log_decision(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "director_decisions.jsonl"
    monkeypatch.setenv("DRIFT_DIRECTOR_AUDIT_LOG", str(log_path))

    log_decision(
        player_id="director1",
        decision="transition",
        reason="target_state=TAKE",
        level_id="level-1",
        session_state="TAKE",
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["player_id"] == "director1"
    assert obj["decision"] == "transition"
    assert obj["level_id"] == "level-1"
    assert obj["session_state"] == "TAKE"
