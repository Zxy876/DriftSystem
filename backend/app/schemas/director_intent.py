"""导演输入框 Intent Schema（v1.21）。

模块角色：对导演输入框内容做结构化校验，为后端路由提供强约束。
不做什么：不解析自然语言、不生成世界补丁、不直接调用 Mineflayer / RCON。
"""
from __future__ import annotations

from typing import Any, Dict, Literal, Annotated, Union

from pydantic import BaseModel, Field


class DirectorInput(BaseModel):
    player_id: str = Field(..., min_length=1, description="发起者玩家标识")
    raw_text: str = Field(..., min_length=1, max_length=512, description="导演输入框的原始文本")
    dry_run: bool = Field(True, description="仅路由与校验，不落库")


class LevelIntent(BaseModel):
    intent_type: Literal["level"] = Field("level", description="意图类型：LevelSession 阶段控制")
    level_id: str = Field(..., min_length=1)
    target_state: str = Field(..., min_length=1)
    actor_id: str | None = Field(default=None)


class TaskIntent(BaseModel):
    intent_type: Literal["task"] = Field("task", description="意图类型：布景任务请求")
    task_id: str = Field(..., min_length=1)
    level_id: str = Field(..., min_length=1)
    assigned_to: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)


class ActorIntent(BaseModel):
    intent_type: Literal["actor"] = Field("actor", description="意图类型：演员控制")
    actor_id: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1, description="有限集合外的值将在路由层被拒绝")
    payload: Dict[str, Any] = Field(default_factory=dict, description="额外参数（受限使用）")

class BuildIntent(BaseModel):
    intent_type: Literal["build"] = Field("build", description="意图类型：施工队任务")
    task_id: str = Field(..., min_length=1)
    blueprint_id: str = Field(..., min_length=1)
    level_id: str = Field(..., min_length=1)
    assigned_to: str = Field("crew_builder_01", min_length=1)
    origin_x: float | None = Field(default=None, description="可选：蓝图原点 X")
    origin_y: float | None = Field(default=None, description="可选：蓝图原点 Y")
    origin_z: float | None = Field(default=None, description="可选：蓝图原点 Z")


DirectorIntent = Annotated[Union[LevelIntent, TaskIntent, ActorIntent, BuildIntent], Field(discriminator="intent_type")]

__all__ = [
    "DirectorInput",
    "DirectorIntent",
    "LevelIntent",
    "TaskIntent",
    "ActorIntent",
    "BuildIntent",
]
