"""Smoke tests for task runtime (Issue 7.2)."""
from pathlib import Path

from app.services.task_runtime.TaskManager import TaskManager


def test_task_runtime_flow(tmp_path: Path) -> None:
    mgr = TaskManager(base_dir=tmp_path)
    mgr.create_task({"task_id": "t1", "level_id": "l1", "assigned_to": "crew", "summary": "demo"})
    mgr.update_status("t1", "done")
    events = list(mgr.list_pending())
    assert events == []
