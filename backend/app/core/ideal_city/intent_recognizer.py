"""Heuristic intent recognition for Ideal City submissions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IntentKind(str, Enum):
    REFRESH_MODS = "refresh_mods"


@dataclass(frozen=True)
class IntentMatch:
    kind: IntentKind
    confidence: float = 1.0


_REFRESH_KEYWORDS = (
    "刷新模组",
    "刷新 mods",
    "更新模组",
    "更新 mods",
    "reload mods",
    "refresh mods",
    "刷新模组缓存",
    "刷新模組",
)


def detect_intent(narrative: str) -> Optional[IntentMatch]:
    """Return an intent match if the input narrative encodes a system command."""

    if not narrative:
        return None
    lowered = narrative.strip().lower()
    compact = lowered.replace(" ", "")
    for keyword in _REFRESH_KEYWORDS:
        key_lower = keyword.lower().replace(" ", "")
        if key_lower and (key_lower in lowered or key_lower in compact):
            return IntentMatch(kind=IntentKind.REFRESH_MODS)
    return None
