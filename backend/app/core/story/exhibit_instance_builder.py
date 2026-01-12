"""Utility helpers for capturing exhibit instances from world patches."""

from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha1
from typing import Any, Dict, Optional

from .exhibit_instance_repository import ExhibitInstance


_STRUCTURAL_KEYS = {
    "build",
    "build_multi",
    "commands",
    "fill",
    "clone",
    "setblock",
    "structure",
    "structure_load",
    "nbt",
    "place",
}


class ExhibitInstanceBuilder:
    """Stateless helper that materialises ExhibitInstance objects from patches.

    The builder performs no curation – it only records patches that have already
    been applied to the world. Callers remain responsible for deciding *when* the
    resulting instances should be saved.
    """

    def build_from_patch(
        self,
        *,
        player_id: str,
        level_id: str,
        exhibit_payload: Optional[Dict[str, str]],
        patch: Optional[Dict[str, Any]],
    ) -> Optional[ExhibitInstance]:
        if not patch:
            return None
        if not exhibit_payload:
            return None

        mc_payload = patch.get("mc") if isinstance(patch, dict) else None
        if not isinstance(mc_payload, dict):
            return None
        if not _contains_structure_change(mc_payload):
            return None

        scenario_id = exhibit_payload.get("scenario_id") or exhibit_payload.get("id") or "default"
        exhibit_id = exhibit_payload.get("id") or exhibit_payload.get("exhibit_id") or scenario_id

        title = exhibit_payload.get("title") if isinstance(exhibit_payload.get("title"), str) else None
        description = exhibit_payload.get("scope") if isinstance(exhibit_payload.get("scope"), str) else None

        payload = {"mc": deepcopy(mc_payload)}

        instance = ExhibitInstance(
            scenario_id=scenario_id,
            exhibit_id=exhibit_id,
            level_id=level_id,
            snapshot_type="world_patch",
            payload=payload,
            created_by=player_id,
            title=title,
            description=description,
        )
        return instance

    @staticmethod
    def fingerprint(instance: ExhibitInstance) -> str:
        """Stable fingerprint for deduplicating instances within a session."""

        payload = instance.payload if isinstance(instance.payload, dict) else {}
        dump = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return sha1(dump.encode("utf-8")).hexdigest()


def _contains_structure_change(mc_payload: Dict[str, Any]) -> bool:
    for key, value in mc_payload.items():
        if key in {"tell", "title", "actionbar", "subtitle", "bossbar", "sound", "particle"}:
            # These are presentation-only side effects and should not be persisted as exhibits.
            continue
        if key in _STRUCTURAL_KEYS:
            return True
        if key == "commands" and isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and _contains_structure_change(value):
            return True
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and _contains_structure_change(item):
                    return True
    return False
