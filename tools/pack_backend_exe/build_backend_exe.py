"""Build the DriftSystem backend into a standalone Windows executable.

This script wraps PyInstaller so we can control build parameters in one
place and keep path handling consistent between Windows and POSIX. It is
cross-platform, but only Windows builds yield a ``.exe`` binary.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, List

try:
    import PyInstaller.__main__  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "PyInstaller is not installed. Please install it before running this script."
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACK_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DIST_DIR = PACK_DIR / "dist"
BUILD_DIR = PACK_DIR / "build"


REQUIRED_DATA_FOLDERS = [
    (BACKEND_DIR / "data", "backend/data"),
    (BACKEND_DIR / "app" / "static", "backend/app/static"),
]


def _format_add_data_arg(src: Path, dest: str) -> str:
    separator = ";" if os.name == "nt" else ":"
    return f"{src}{separator}{dest}"


def _iter_existing_data_args() -> Iterable[str]:
    for src, dest in REQUIRED_DATA_FOLDERS:
        if src.exists():
            yield f"--add-data={_format_add_data_arg(src, dest)}"


def _pyinstaller_args() -> List[str]:
    args: List[str] = [
        str(PACK_DIR / "run_backend.py"),
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name=DriftSystemBackend",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        "--paths",
        str(BACKEND_DIR),
    ]

    args.extend(_iter_existing_data_args())

    # Ensure PyInstaller can locate the dynamically loaded optional modules.
    hidden_imports = [
        "app.api.tree_api",
        "app.api.dsl_api",
        "app.api.hint_api",
        "app.api.world_api",
        "app.api.story_api",
        "app.api.npc_api",
        "app.api.tutorial_api",
        "app.api.minimap_api",
        "app.routers.ai_router",
        "app.routers.minimap",
        "app.core.ai.deepseek_agent",
        "app.core.story.story_engine",
        "app.core.story.story_loader",
        "app.core.world.minimap",
        "app.core.world.minimap_renderer",
        "app.core.world.scene_generator",
        "app.core.world.trigger",
        "app.core.npc.npc_engine",
        "app.core.quest.runtime",
        "app.core.events.event_manager",
    ]
    for module in hidden_imports:
        args.append(f"--hidden-import={module}")

    return args


def build() -> None:
    if not BACKEND_DIR.exists():
        raise SystemExit(f"backend directory not found: {BACKEND_DIR}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    PyInstaller.__main__.run(_pyinstaller_args())


if __name__ == "__main__":
    build()
