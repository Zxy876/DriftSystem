"""Static exhibit registry for bridging levels to curatorial metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, Optional


@dataclass(frozen=True)
class ExhibitSlot:
    """Minimal exhibit metadata surfaced to story and CityPhone layers."""

    exhibit_id: str
    scenario_id: Optional[str] = None
    title: Optional[str] = None
    scope: Optional[str] = None

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "id": self.exhibit_id,
            "scenario_id": self.scenario_id,
            "title": self.title,
            "scope": self.scope,
        }


class ExhibitRegistry:
    """Filesystem-backed lookup table for level → exhibit bindings."""

    def __init__(self, registry_path: Optional[Path] = None) -> None:
        backend_root = Path(__file__).resolve().parents[3]
        default_path = backend_root / "data" / "ideal_city" / "exhibits" / "registry.json"
        self._path = registry_path or default_path
        self._cache: Optional[Dict[str, object]] = None
        self._lock = Lock()

    def lookup(self, level_id: Optional[str], *, scenario_hint: Optional[str] = None) -> Optional[ExhibitSlot]:
        payload = self._load()
        exhibits = payload.get("exhibits") if isinstance(payload.get("exhibits"), dict) else {}
        levels = payload.get("levels") if isinstance(payload.get("levels"), dict) else {}
        default_id = payload.get("default_exhibit_id") if isinstance(payload.get("default_exhibit_id"), str) else None

        exhibit_id: Optional[str] = None

        if scenario_hint:
            exhibit_id = self._match_scenario_hint(exhibits, scenario_hint)

        if not exhibit_id and isinstance(level_id, str):
            mapping = levels.get(level_id)
            if isinstance(mapping, dict):
                mapped_id = mapping.get("exhibit_id")
                if isinstance(mapped_id, str) and mapped_id:
                    exhibit_id = mapped_id
            elif isinstance(mapping, str) and mapping:
                exhibit_id = mapping

        if not exhibit_id:
            exhibit_id = default_id

        if not exhibit_id:
            return None

        exhibit_cfg = exhibits.get(exhibit_id)
        if not isinstance(exhibit_cfg, dict):
            return None

        scenario_id = exhibit_cfg.get("scenario_id") if isinstance(exhibit_cfg.get("scenario_id"), str) else exhibit_id
        title = exhibit_cfg.get("title") if isinstance(exhibit_cfg.get("title"), str) else None
        scope = exhibit_cfg.get("scope") if isinstance(exhibit_cfg.get("scope"), str) else None

        return ExhibitSlot(
            exhibit_id=exhibit_id,
            scenario_id=scenario_id,
            title=title,
            scope=scope,
        )

    def _match_scenario_hint(self, exhibits: Dict[str, Dict[str, object]], scenario_hint: str) -> Optional[str]:
        normalized = scenario_hint.strip().lower()
        if not normalized:
            return None

        direct = exhibits.get(scenario_hint)
        if isinstance(direct, dict):
            return scenario_hint

        for exhibit_id, config in exhibits.items():
            aliases = config.get("aliases") if isinstance(config, dict) else None
            if not isinstance(aliases, list):
                continue
            for alias in aliases:
                if isinstance(alias, str) and alias.strip().lower() == normalized:
                    return exhibit_id
        return None

    def _load(self) -> Dict[str, object]:
        with self._lock:
            if self._cache is not None:
                return self._cache
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            self._cache = data if isinstance(data, dict) else {}
            return self._cache


# Shared singleton for callers that do not need custom registry paths.
DEFAULT_EXHIBIT_REGISTRY = ExhibitRegistry()
