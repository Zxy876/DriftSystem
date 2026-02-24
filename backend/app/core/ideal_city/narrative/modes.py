from __future__ import annotations

from enum import Enum


class NarrativeMode(Enum):
    IDEAL_CITY = "ideal_city"
    REUNION = "reunion"
    EXPERIMENTAL = "experimental"
    CINEMATIC = "cinematic"


ACTIVE_NARRATIVE_MODE = NarrativeMode.REUNION
