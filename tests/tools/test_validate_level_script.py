"""validate_level_script.py CLI 测试。

模块角色：验证 CLI 对正确与错误 JSON 的返回码与错误输出。
不做什么：不测真实文件系统遍历，只用临时文件。
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT / "tools"
for path in (ROOT, TOOLS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from validate_level_script import main


@pytest.fixture()
def tmp_level(tmp_path: Path) -> Path:
    data = {
        "level_id": "scene_001_market_night",
        "title": "夜市 · 初遇",
        "version": "1.0.0",
        "set_design": {
            "allowed_region": [0, 0, 0, 1, 1, 1],
            "required_props": [
                {"block": "minecraft:soul_lantern", "tag": "main_light"}
            ],
        },
        "actors": [
            {
                "actor_id": "npc_vendor",
                "role": "vendor",
                "memory_seed": "friendly",
                "spawn_point": [0, 64, 0],
            }
        ],
        "beats": [
            {
                "beat_id": "beat_01",
                "description": "灯亮起",
                "requirements": ["main_light:on"],
                "actor_actions": ["npc_vendor:look_up"],
            }
        ],
    }
    path = tmp_path / "level.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_cli_success(tmp_level: Path) -> None:
    """合法脚本返回 0。"""

    rc = main([str(tmp_level)])
    assert rc == 0


def test_cli_strict_failure(tmp_level: Path) -> None:
    """非法脚本在 strict 下返回非零并打印错误。"""

    broken = tmp_level.with_name("broken.json")
    # 移除必填字段 set_design 触发校验失败
    data = json.loads(tmp_level.read_text(encoding="utf-8"))
    data.pop("set_design")
    broken.write_text(json.dumps(data), encoding="utf-8")

    rc = main([str(broken), "--strict"])
    assert rc == 1