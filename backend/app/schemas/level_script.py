"""Level Script schema definitions for v1.21.

模块角色：定义拍摄关卡（Level-as-Script）的合法结构，提供 Pydantic 模型用于后续校验。
不做什么：不负责磁盘扫描、状态迁移或任何世界写入，仅做结构约束与解析。
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 约束类型定义
BoundingBox = Tuple[int, int, int, int, int, int]
Vec3 = Tuple[int, int, int]


class RequiredProp(BaseModel):
    """关卡布景所需的道具条目。"""

    model_config = ConfigDict(extra="forbid")

    block: str = Field(..., min_length=1, description="Minecraft 方块 ID（如 minecraft:soul_lantern）")
    tag: str = Field(..., min_length=1, description="道具在剧本中的唯一标签")


class SetDesign(BaseModel):
    """布景定义，仅描述需要准备的空间与道具，不包含执行细节。"""

    model_config = ConfigDict(extra="forbid")

    allowed_region: BoundingBox = Field(
        ..., description="允许布景的世界边界，格式为 [x1, y1, z1, x2, y2, z2]"
    )
    required_props: List[RequiredProp] = Field(
        default_factory=list,
        description="布景团队必须准备的道具清单",
    )

    @field_validator("allowed_region")
    @classmethod
    def validate_region(cls, value: BoundingBox) -> BoundingBox:
        if len(value) != 6:
            msg = "allowed_region must contain exactly 6 integers"
            raise ValueError(msg)
        return value


class ActorEntry(BaseModel):
    """演员配置，定义角色定位与默认记忆种子。"""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = Field(..., min_length=1, description="演员唯一标识")
    role: str = Field(..., min_length=1, description="演员角色定位，例如 vendor")
    memory_seed: str = Field(..., min_length=1, description="演员初始人格 / 记忆标签")
    spawn_point: Vec3 = Field(..., description="演员出现坐标，顺序为 [x, y, z]")

    @field_validator("spawn_point")
    @classmethod
    def validate_spawn(cls, value: Vec3) -> Vec3:
        if len(value) != 3:
            msg = "spawn_point must contain exactly 3 integers"
            raise ValueError(msg)
        return value


class BeatEntry(BaseModel):
    """剧情节拍，描述拍摄时的动作与依赖。"""

    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(..., min_length=1, description="节拍唯一标识")
    description: str = Field(..., min_length=1, description="节拍描述文字")
    requirements: List[str] = Field(
        default_factory=list,
        description="执行本节拍前必须满足的布景 / 道具状态标签",
    )
    actor_actions: List[str] = Field(
        default_factory=list,
        description="节拍内演员需要执行的动作（仅描述，不携带命令）",
    )


class LevelScript(BaseModel):
    """顶层 Level Script 模型，约束 v1.21 的剧本结构。"""

    model_config = ConfigDict(extra="forbid")

    level_id: str = Field(..., min_length=1, description="关卡唯一 ID")
    title: str = Field(..., min_length=1, description="关卡标题")
    version: str = Field(..., min_length=1, description="剧本版本号")
    set_design: SetDesign
    actors: List[ActorEntry] = Field(default_factory=list, description="参与表演的演员清单")
    beats: List[BeatEntry] = Field(default_factory=list, description="拍摄节拍序列")


def load_level_script(path: str | Path) -> LevelScript:
    """从 JSON 文件加载并校验 Level Script。"""

    data_path = Path(path)
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    return LevelScript.model_validate(raw)


__all__ = [
    "ActorEntry",
    "BeatEntry",
    "LevelScript",
    "RequiredProp",
    "SetDesign",
    "load_level_script",
]
