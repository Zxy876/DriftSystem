"""Tests for TaskManager (Issue 3.2)."""
from datetime import datetime, timezone
from pathlib import Path
import json

from app.services.task_runtime.TaskManager import TaskManager


def fixed_now() -> datetime:
    return datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)


def test_create_task_writes_jsonl(tmp_path: Path) -> None:
    mgr = TaskManager(base_dir=tmp_path, now_provider=fixed_now)
    record = mgr.create_task(
        {
            "task_id": "task-1",
            "level_id": "level-1",
            "assigned_to": "crew-a",
            "summary": "do something",
        }
    )

    assert record.status == "pending"
    run_dir = tmp_path / "20260122T120000Z"
    log_path = run_dir / "task.jsonl"
    assert log_path.exists()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["type"] == "create"
    assert obj["record"]["task_id"] == "task-1"


def test_update_and_event_appended(tmp_path: Path) -> None:
    mgr = TaskManager(base_dir=tmp_path, now_provider=fixed_now)
    mgr.create_task(
        {
            "task_id": "task-2",
            "level_id": "level-2",
            "assigned_to": "crew-b",
            "summary": "prep stage",
        }
    )
    mgr.update_status("task-2", "done")
    mgr.append_event("task-2", {"msg": "ok"})

    log_path = tmp_path / "20260122T120000Z" / "task.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    types = [json.loads(line)["type"] for line in lines]
    assert types == ["create", "update", "event"]


def test_list_pending(tmp_path: Path) -> None:
    mgr = TaskManager(base_dir=tmp_path, now_provider=fixed_now)
    mgr.create_task(
        {
            "task_id": "task-pending",
            "level_id": "level-1",
            "assigned_to": "crew-a",
            "summary": "pending task",
        }
    )
    mgr.create_task(
        {
            "task_id": "task-done",
            "level_id": "level-1",
            "assigned_to": "crew-a",
            "summary": "done task",
            "status": "done",
        }
    )

    pending = list(mgr.list_pending())
    assert len(pending) == 1
    assert pending[0]["task_id"] == "task-pending"
