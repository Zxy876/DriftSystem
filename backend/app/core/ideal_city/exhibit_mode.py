"""Exhibit mode state machine for CityPhone."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ExhibitMode(str, Enum):
    """Enumerates curatorial modes exposed to the CityPhone client."""

    ARCHIVE = "archive"
    PRODUCTION = "production"


class ExhibitModeState(BaseModel):
    """Resolved exhibit mode enriched with human readable guidance."""

    mode: ExhibitMode = ExhibitMode.ARCHIVE
    label: str = "看展模式 · Archive"
    description: List[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None
    source: str = "narrative"


class ExhibitModeResolver:
    """Resolve exhibit mode based on backend + protocol signals."""

    def __init__(
        self,
        *,
        archival_refresh_hours: int = 24,
    ) -> None:
        # 市场默认以档案语态运行，仅在最近档案更新时补充说明。
        self._recent_window = timedelta(hours=archival_refresh_hours)

    def resolve(
        self,
        *,
        has_active_plan: bool,
        has_execution_record: bool,
        last_archival_update: Optional[datetime] = None,
    ) -> ExhibitModeState:
        description: List[str] = [
            "展馆以档案方式开放，重在回顾历史与未解问题。",
        ]

        if last_archival_update is not None:
            now = datetime.now(timezone.utc)
            age = now - last_archival_update
            if age <= self._recent_window:
                description.append("档案记录刚刚更新，展厅正在调校陈列叙述。")
            else:
                hours = max(int(age.total_seconds() // 3600), 1)
                description.append(f"最近一次档案整理约在 {hours} 小时前。")

        if has_execution_record:
            description.append("最新的建造痕迹已编入档案，展厅展示将按记忆节奏同步。")
        elif has_active_plan:
            description.append("档案馆保留了一份建造计划，等待世界留下执行记录。")
        else:
            description.append("当前展厅侧重回溯历史与缺失片段，欢迎自行探索。")

        merged: List[str] = []
        for line in description:
            cleaned = line.strip()
            if not cleaned or cleaned in merged:
                continue
            merged.append(cleaned)

        return ExhibitModeState(
            mode=ExhibitMode.ARCHIVE,
            label="看展模式 · Archive",
            description=merged,
            updated_at=last_archival_update,
            source="narrative",
        )
