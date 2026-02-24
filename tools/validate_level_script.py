"""CLI 校验工具：验证 v1.21 Level Script JSON。

模块角色：读取 JSON，使用 `app.schemas.level_script.LevelScript` 校验结构。
不做什么：不写数据库、不触发状态机、不写世界。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.schemas.level_script import LevelScript


def validate_level_script(path: Path, strict: bool = False) -> None:
    raw: Any
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - I/O 错误信息直接抛出
        raise SystemExit(f"读取文件失败: {exc}")

    try:
        LevelScript.model_validate(raw)
    except Exception as exc:
        if strict:
            raise SystemExit(f"校验失败: {exc}")
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate v1.21 Level Script JSON")
    parser.add_argument("path", type=Path, help="Path to level script JSON")
    parser.add_argument("--strict", action="store_true", help="打印详细错误并以 1 退出")

    args = parser.parse_args(argv)

    try:
        validate_level_script(args.path, strict=args.strict)
    except SystemExit as exc:  # 捕获手动 exit
        code = exc.code
        try:
            return int(code) if code is not None else 1
        except (TypeError, ValueError):
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())