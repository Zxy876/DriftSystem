"""Level Script Schema 测试。

模块角色：验证 v1.21 Level Script Pydantic 模型的基本约束。
不做什么：不测试磁盘遍历或 API，仅校验结构与错误路径。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.level_script import LevelScript, load_level_script


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = PROJECT_ROOT / "docs" / "v1.21"


def _load_example_dict() -> dict:
    example_path = DOCS_ROOT / "example_level.json"
    return json.loads(example_path.read_text(encoding="utf-8"))


def test_example_level_script_can_be_loaded() -> None:
    """验证示例 JSON 可被成功解析。"""

    example = load_level_script(DOCS_ROOT / "example_level.json")
    assert example.level_id == "scene_001_market_night"
    assert example.set_design.required_props[0].block == "minecraft:soul_lantern"
    assert len(example.beats) == 2


@pytest.mark.parametrize(
    "field, payload",
    [
        ("allowed_region", [0, 0, 0, 1, 1]),
        ("spawn_point", [0, 0]),
    ],
)
def test_invalid_vector_lengths_raise(field: str, payload: list[int]) -> None:
    """长度不符合要求的向量应触发校验错误。"""

    data = _load_example_dict()
    if field == "allowed_region":
        data["set_design"][field] = payload
    else:
        data["actors"][0][field] = payload

    with pytest.raises(ValueError):
        LevelScript.model_validate(data)