"""Entry point used by the packaged FastAPI backend executable.

This script is intentionally kept outside the backend package so we can
bootstrap the runtime environment in both development (PyInstaller build)
and the frozen executable. It locates the original backend directory,
adds it to the Python path, and then launches Uvicorn against
``app.main:app`` exactly like ``uvicorn app.main:app`` does today.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def _resolve_project_root() -> Path:
    """Return the project root regardless of frozen state."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller extracts bundled assets into ``_MEIPASS``.
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def _prepare_backend_path() -> Path:
    project_root = _resolve_project_root()
    backend_dir = project_root / "backend"
    if not backend_dir.exists():
        raise RuntimeError(f"backend directory not found at {backend_dir}")

    # Ensure Python can import ``app`` and siblings from the original backend.
    backend_path = str(backend_dir)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    # ``app`` package imports already happen during Uvicorn startup, but we
    # eagerly import here so PyInstaller can discover every dependency.
    import app.main  # noqa: F401  # pylint: disable=unused-import

    # Match the original working-directory expectations.
    os.chdir(backend_path)

    return backend_dir


def main() -> None:
    _prepare_backend_path()

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        workers=1,
    )


if __name__ == "__main__":
    main()
