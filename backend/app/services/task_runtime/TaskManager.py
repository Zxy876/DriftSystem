"""TaskManager for crew task runtime (Issue 3.2).

模块角色：管理布景团队任务的生命周期，使用 jsonl 记录写入。默认仅记录，不直接执行任何游戏指令。
不做什么：不与 mineflayer / Minecraft 交互，不修改世界状态；仅做任务持久化与查询。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field

RUNS_DIR_ENV = "DRIFT_CREW_RUNS_DIR"
DEFAULT_LOG_ROOT = Path("backend/logs/crew_runs")
TIMESTAMP_FMT = "%Y%m%dT%H%M%SZ"


class TaskRecord(BaseModel):
    """结构化 Task 记录，便于校验与序列化。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., min_length=1)
    level_id: str = Field(..., min_length=1)
    assigned_to: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    events: List[Dict] = Field(default_factory=list)
    created_at: str
    updated_at: str


@dataclass
class TaskManager:
    """简易 JSONL TaskManager。"""

    base_dir: Path | None = None
    now_provider: Optional[Callable[[], datetime]] = field(default=None)

    def __post_init__(self) -> None:
        env_path = os.environ.get(RUNS_DIR_ENV)
        root = Path(env_path) if env_path else self.base_dir or DEFAULT_LOG_ROOT
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._run_dir_cached: Optional[Path] = None

    def _utcnow(self) -> datetime:
        if self.now_provider is not None:
            return self.now_provider()
        return datetime.now(timezone.utc)

    def _run_dir(self) -> Path:
        if self._run_dir_cached is None:
            ts = self._utcnow().strftime(TIMESTAMP_FMT)
            run_dir = self.root / ts
            run_dir.mkdir(parents=True, exist_ok=True)
            self._run_dir_cached = run_dir
        return self._run_dir_cached

    def _log_path(self, run_dir: Path) -> Path:
        return run_dir / "task.jsonl"

    def _append_jsonl(self, path: Path, record: Dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def create_task(self, task: Dict) -> TaskRecord:
        run_dir = self._run_dir()
        log_path = self._log_path(run_dir)
        now = self._utcnow().strftime(TIMESTAMP_FMT)

        record = TaskRecord.model_validate(
            {
                **task,
                "status": task.get("status", "pending"),
                "events": task.get("events", []),
                "created_at": now,
                "updated_at": now,
            }
        )
        self._append_jsonl(log_path, {"type": "create", "record": record.model_dump()})
        return record

    def update_status(self, task_id: str, new_status: str) -> TaskRecord:
        run_dir = self._run_dir()
        log_path = self._log_path(run_dir)
        now = self._utcnow().strftime(TIMESTAMP_FMT)
        record = TaskRecord.model_validate(
            {
                "task_id": task_id,
                "level_id": "unknown",
                "assigned_to": "unknown",
                "summary": "",
                "status": new_status,
                "events": [],
                "created_at": now,
                "updated_at": now,
            }
        )
        self._append_jsonl(log_path, {"type": "update", "record": record.model_dump()})
        return record

    def append_event(self, task_id: str, event: Dict) -> Dict:
        run_dir = self._run_dir()
        log_path = self._log_path(run_dir)
        payload = {"type": "event", "task_id": task_id, "event": event, "timestamp": self._utcnow().strftime(TIMESTAMP_FMT)}
        self._append_jsonl(log_path, payload)
        return payload

    def list_pending(self) -> Iterable[Dict]:
        # 简化实现：读取最新 run_dir 的 task.jsonl 中 status=pending 的 create 记录
        if not self.root.exists():
            return []
        run_dirs = sorted([p for p in self.root.iterdir() if p.is_dir()], reverse=True)
        for run_dir in run_dirs:
            log_path = self._log_path(run_dir)
            if not log_path.exists():
                continue
            pending: List[Dict] = []
            with log_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") == "create":
                        rec = obj.get("record", {})
                        if rec.get("status") == "pending":
                            pending.append(rec)
            if pending:
                return pending
        return []


__all__ = ["TaskManager", "TaskRecord"]
