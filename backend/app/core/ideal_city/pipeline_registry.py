"""Singleton accessor for the Ideal City pipeline.

This module centralises construction of the pipeline so that multiple API
routers or background bridges can reuse the same instance without importing
FastAPI route modules or triggering circular dependencies.
"""
from __future__ import annotations

from threading import Lock
from typing import Optional

from .pipeline import IdealCityPipeline

__all__ = ["get_pipeline", "reset_pipeline"]

_lock = Lock()
_instance: Optional[IdealCityPipeline] = None


def get_pipeline() -> IdealCityPipeline:
    """Return a shared IdealCityPipeline instance.

    The pipeline is initialised lazily so that environment overrides such as
    ``IDEAL_CITY_DATA_ROOT`` are evaluated at the time of the first access.
    Subsequent callers receive the same instance.
    """

    global _instance
    with _lock:
        if _instance is None:
            _instance = IdealCityPipeline()
        return _instance


def reset_pipeline() -> None:
    """Reset the cached pipeline instance (primarily for tests)."""

    global _instance
    with _lock:
        _instance = None
