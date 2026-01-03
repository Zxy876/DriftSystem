"""Queue management for Ideal City build plans."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .build_plan import BuildPlan, BuildPlanStatus


@dataclass
class BuildSchedulerConfig:
    root_dir: Path
    queue_filename: str = "build_queue.jsonl"


class BuildScheduler:
    """Append-only queue storing build plans for downstream executors."""

    def __init__(self, config: BuildSchedulerConfig) -> None:
        self.config = config
        self.config.root_dir.mkdir(parents=True, exist_ok=True)
        (self.config.root_dir / "completed").mkdir(parents=True, exist_ok=True)
        (self.config.root_dir / "failed").mkdir(parents=True, exist_ok=True)

    @property
    def queue_path(self) -> Path:
        return self.config.root_dir / self.config.queue_filename

    def enqueue(self, plan: BuildPlan) -> None:
        plan.status = BuildPlanStatus.queued
        with self.queue_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(plan.to_storage_dict(), ensure_ascii=False) + "\n")

    def load_queue(self, limit: Optional[int] = None) -> List[BuildPlan]:
        if not self.queue_path.exists():
            return []
        plans: List[BuildPlan] = []
        with self.queue_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                plan = BuildPlan.model_validate(payload)
                plans.append(plan)
                if limit is not None and len(plans) >= limit:
                    break
        return plans

    def archive(self, plan: BuildPlan, folder: str = "completed") -> Path:
        target_dir = self.config.root_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{plan.plan_id}.json"
        plan.status = BuildPlanStatus.completed if folder == "completed" else BuildPlanStatus.blocked
        target_path.write_text(json.dumps(plan.to_storage_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return target_path

    def has_pending(self) -> bool:
        return bool(self.load_queue(limit=1))

    def iter_queue_paths(self) -> Iterable[Path]:
        if not self.queue_path.exists():
            return []
        return [self.queue_path]

    def pop_next(self) -> Optional[BuildPlan]:
        if not self.queue_path.exists():
            return None
        selected: Optional[BuildPlan] = None
        remaining: List[str] = []
        with self.queue_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                if not raw_line.strip():
                    continue
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    remaining.append(raw_line)
                    continue
                if selected is None:
                    try:
                        plan = BuildPlan.model_validate(payload)
                    except Exception:
                        remaining.append(raw_line)
                        continue
                    plan.status = BuildPlanStatus.queued
                    selected = plan
                    continue
                remaining.append(raw_line)
        if selected is None:
            return None
        with self.queue_path.open("w", encoding="utf-8") as handle:
            handle.writelines(remaining)
        return selected

    def consume_all(self) -> List[BuildPlan]:
        plans: List[BuildPlan] = []
        while True:
            plan = self.pop_next()
            if plan is None:
                break
            plans.append(plan)
        return plans
