"""Crew Task schema definitions for v1.21.

模块角色：定义布景团队（Crew）可执行的任务结构，确保任务内容仅包含受控指令。
不做什么：不下发或执行任何游戏指令，不写入世界状态，仅负责任务数据的结构校验。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional, Tuple

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Vec3 = Tuple[int, int, int]
Region = Tuple[int, int, int, int, int, int]
AllowedAction = Literal["setblock", "clear", "travel"]


class CrewAction(BaseModel):
    """单条可执行动作。限制为 setblock/clear/travel 三种。"""

    model_config = ConfigDict(extra="forbid")

    action: AllowedAction = Field(..., description="动作类型：setblock/clear/travel")
    position: Optional[Vec3] = Field(
        default=None,
        description="单点坐标，setblock/travel 需要，格式为 [x,y,z]",
    )
    block: Optional[str] = Field(
        default=None,
        description="setblock 使用的方块 ID（如 minecraft:oak_planks）",
        min_length=1,
    )
    region: Optional[Region] = Field(
        default=None,
        description="clear 使用的区域边界，格式 [x1,y1,z1,x2,y2,z2]",
    )
    note: Optional[str] = Field(default=None, description="可选说明/安全提示")

    @field_validator("position")
    @classmethod
    def validate_position(cls, value: Optional[Vec3]) -> Optional[Vec3]:
        if value is None:
            return value
        if len(value) != 3:
            msg = "position must contain exactly 3 integers"
            raise ValueError(msg)
        return value

    @field_validator("region")
    @classmethod
    def validate_region(cls, value: Optional[Region]) -> Optional[Region]:
        if value is None:
            return value
        if len(value) != 6:
            msg = "region must contain exactly 6 integers"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_by_action(self) -> "CrewAction":
        if self.action == "setblock":
            if self.position is None:
                msg = "setblock requires position"
                raise ValueError(msg)
            if self.block is None:
                msg = "setblock requires block"
                raise ValueError(msg)
        if self.action == "clear":
            if self.region is None:
                msg = "clear requires region"
                raise ValueError(msg)
        if self.action == "travel":
            if self.position is None:
                msg = "travel requires position"
                raise ValueError(msg)
        return self


class CrewTask(BaseModel):
    """顶层 Crew Task 模型，约束布景团队任务内容。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., min_length=1, description="任务唯一 ID")
    level_id: str = Field(..., min_length=1, description="关联的关卡 ID")
    assigned_to: str = Field(..., min_length=1, description="执行该任务的机器人/人员标识")
    summary: str = Field(..., min_length=1, description="任务摘要")
    actions: List[CrewAction] = Field(default_factory=list, description="需按顺序执行的动作列表")


def load_crew_task(path: str | Path) -> CrewTask:
    """从 JSON 文件加载并校验 Crew Task。"""

    data_path = Path(path)
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    return CrewTask.model_validate(raw)


__all__ = [
    "AllowedAction",
    "CrewAction",
    "CrewTask",
    "load_crew_task",
]
