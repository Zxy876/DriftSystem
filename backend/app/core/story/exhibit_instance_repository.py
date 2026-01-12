"""Filesystem-backed repository for exhibit instance persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ExhibitInstance:
    """Serialized exhibit artefact captured from a scenario run."""

    scenario_id: str
    exhibit_id: str
    level_id: str
    snapshot_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    instance_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=_now_iso)
    created_by: Optional[str] = None
    manifest_ref: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "scenario_id": self.scenario_id,
            "exhibit_id": self.exhibit_id,
            "level_id": self.level_id,
            "snapshot_type": self.snapshot_type,
            "payload": self.payload,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "manifest_ref": self.manifest_ref,
            "title": self.title,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ExhibitInstance":
        copy: Dict[str, Any] = dict(payload or {})
        if not isinstance(copy.get("payload"), dict):
            copy["payload"] = {}
        return cls(**copy)  # type: ignore[arg-type]

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "scenario_id": self.scenario_id,
            "exhibit_id": self.exhibit_id,
            "level_id": self.level_id,
            "snapshot_type": self.snapshot_type,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "title": self.title,
            "description": self.description,
            "manifest_ref": self.manifest_ref,
        }


class ExhibitInstanceRepository:
    """JSON-backed repository storing exhibit instances per scenario."""

    def __init__(self, root: Optional[Path] = None) -> None:
        backend_root = Path(__file__).resolve().parents[3]
        default_root = backend_root / "data" / "ideal_city" / "exhibit_instances"
        self._root = root or default_root
        self._lock = Lock()
        self._root.mkdir(parents=True, exist_ok=True)

    def save_instance(self, instance: ExhibitInstance) -> ExhibitInstance:
        scenario_dir = self._root / self._sanitize(instance.scenario_id)
        scenario_dir.mkdir(parents=True, exist_ok=True)
        path = scenario_dir / f"{instance.instance_id}.json"
        with self._lock:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(instance.to_dict(), handle, ensure_ascii=False, indent=2)
            self._write_index_entry(instance)
        return instance

    def list_instances(
        self,
        *,
        scenario_id: Optional[str] = None,
        exhibit_id: Optional[str] = None,
        snapshot_types: Optional[Iterable[str]] = None,
    ) -> List[ExhibitInstance]:
        scenarios: List[str]
        if scenario_id:
            scenarios = [scenario_id]
        else:
            scenarios = sorted([entry.name for entry in self._root.iterdir() if entry.is_dir()])
        types = {stype for stype in (snapshot_types or []) if stype}
        collected: List[ExhibitInstance] = []
        for scenario in scenarios:
            index = self._load_index(scenario)
            for metadata in index:
                if exhibit_id and metadata.get("exhibit_id") != exhibit_id:
                    continue
                if types and metadata.get("snapshot_type") not in types:
                    continue
                instance = self._load_instance(metadata.get("instance_id"), scenario)
                if instance is None:
                    continue
                collected.append(instance)
        return collected

    def get_instances_for_level(
        self,
        level_id: str,
        *,
        scenario_id: Optional[str] = None,
        exhibit_id: Optional[str] = None,
    ) -> List[ExhibitInstance]:
        candidates = self.list_instances(scenario_id=scenario_id, exhibit_id=exhibit_id)
        return [item for item in candidates if item.level_id == level_id]

    def load_instance(self, instance_id: str, scenario_id: str) -> Optional[ExhibitInstance]:
        return self._load_instance(instance_id, scenario_id)

    def _load_instance(self, instance_id: Optional[str], scenario_id: str) -> Optional[ExhibitInstance]:
        if not instance_id:
            return None
        path = self._root / self._sanitize(scenario_id) / f"{instance_id}.json"
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return ExhibitInstance.from_dict(payload)
        except Exception:
            return None

    def _write_index_entry(self, instance: ExhibitInstance) -> None:
        scenario = self._sanitize(instance.scenario_id)
        index_path = self._root / scenario / "index.json"
        index = self._load_index(scenario)
        filtered = [meta for meta in index if meta.get("instance_id") != instance.instance_id]
        filtered.append(instance.to_metadata())
        filtered.sort(key=lambda meta: meta.get("created_at") or "")
        with index_path.open("w", encoding="utf-8") as handle:
            json.dump({"instances": filtered}, handle, ensure_ascii=False, indent=2)

    def _load_index(self, scenario: str) -> List[Dict[str, Any]]:
        scenario_dir = self._root / self._sanitize(scenario)
        index_path = scenario_dir / "index.json"
        if not index_path.exists():
            return []
        try:
            with index_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []
        entries = payload.get("instances") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return []
        output: List[Dict[str, Any]] = []
        for item in entries:
            if isinstance(item, dict) and item.get("instance_id"):
                output.append(dict(item))
        return output

    def _sanitize(self, segment: str) -> str:
        token = segment or "default"
        return "".join(ch for ch in token if ch.isalnum() or ch in {"-", "_", "."}) or "default"
