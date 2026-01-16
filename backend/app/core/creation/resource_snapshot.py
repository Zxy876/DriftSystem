"""Resource snapshot utilities for creation planning."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.world.resource_sanitizer import sanitize_command_list, sanitize_resource_location


logger = logging.getLogger(__name__)


BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESOURCE_CATALOG = BACKEND_ROOT / "data" / "transformer" / "resource_catalog.json"
DEFAULT_RESOURCE_SEED = BACKEND_ROOT / "data" / "transformer" / "resource_catalog.seed.json"


@dataclass
class ResourceRecord:
    """Descriptor for a single buildable resource."""

    resource_id: str
    label: str
    category: str = "block"
    aliases: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    available: Optional[int] = None
    commands: List[str] = field(default_factory=list)

    def match_score(self, token: str) -> float:
        """Compute an affinity score between this record and a material token."""

        if not token:
            return 0.0
        token_norm = token.strip().lower()
        if not token_norm:
            return 0.0
        aliases = [alias.strip().lower() for alias in self.aliases if alias and isinstance(alias, str)]
        label_norm = self.label.strip().lower()

        scores: List[float] = []
        if token_norm == label_norm:
            scores.append(1.0)
        if token_norm in label_norm or label_norm in token_norm:
            scores.append(0.85)
        for alias in aliases:
            if not alias:
                continue
            if token_norm == alias:
                scores.append(1.0)
            elif token_norm in alias or alias in token_norm:
                scores.append(0.8)
        if token_norm in {tag.lower() for tag in self.tags}:
            scores.append(0.7)
        if not scores:
            # prefer partial overlap via common prefix or suffix
            for alias in aliases + [label_norm]:
                if alias.startswith(token_norm) or alias.endswith(token_norm):
                    scores.append(0.4)
                    break
        return max(scores) if scores else 0.0

    def to_payload(self) -> Dict[str, object]:
        return {
            "resource_id": self.resource_id,
            "label": self.label,
            "category": self.category,
            "aliases": list(self.aliases),
            "tags": list(self.tags),
            "available": self.available,
            "commands": list(self.commands),
        }


@dataclass
class ResourceSnapshot:
    """Snapshot of buildable resources available to the transformer."""

    resources: List[ResourceRecord] = field(default_factory=list)
    generated_at: Optional[str] = None

    def find_candidates(self, token: str, *, limit: int = 3, threshold: float = 0.35) -> List[Tuple[ResourceRecord, float]]:
        """Return best-matching resources for the provided token."""

        scored: List[Tuple[ResourceRecord, float]] = []
        for record in self.resources:
            score = record.match_score(token)
            if score >= threshold:
                scored.append((record, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def to_payload(self) -> Dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "resources": [record.to_payload() for record in self.resources],
        }


class ResourceCatalog:
    """Loader backed by the static resource catalog JSON file."""

    def __init__(
        self,
        path: Path = DEFAULT_RESOURCE_CATALOG,
        *,
        seed_path: Path = DEFAULT_RESOURCE_SEED,
        auto_refresh: bool = True,
    ) -> None:
        from .snapshot_builder import ResourceSnapshotBuilder

        self._path = path
        self._seed_path = seed_path
        self._auto_refresh = auto_refresh
        self._builder = ResourceSnapshotBuilder(
            backend_root=BACKEND_ROOT,
            output_path=self._path,
            seed_path=self._seed_path,
        )

    @lru_cache(maxsize=1)
    def load_snapshot(self) -> ResourceSnapshot:
        if self._auto_refresh:
            try:
                snapshot = self._builder.generate()
                return snapshot
            except Exception:  # pragma: no cover - fallback path
                logger.exception("resource_catalog_auto_refresh_failed")
        payload = self._load_payload(self._path)
        return self._snapshot_from_payload(payload)

    def invalidate(self) -> None:
        self.load_snapshot.cache_clear()  # type: ignore[attr-defined]

    @staticmethod
    def _load_payload(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return {}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _safe_int(value: object) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _snapshot_from_payload(self, payload: Dict[str, object]) -> ResourceSnapshot:
        resources_payload = payload.get("resources") if isinstance(payload, dict) else None
        resources: List[ResourceRecord] = []
        if isinstance(resources_payload, Sequence):
            for entry in resources_payload:
                if not isinstance(entry, dict):
                    continue
                resource_id = str(entry.get("resource_id") or "").strip()
                label = str(entry.get("label") or "").strip()
                if not resource_id or not label:
                    continue
                sanitized_id = sanitize_resource_location(resource_id, context="catalog_loader")
                if sanitized_id != resource_id:
                    logger.warning(
                        "resource_id_normalised loader original=%s sanitised=%s", resource_id, sanitized_id
                    )
                    resource_id = sanitized_id
                commands_raw = [
                    str(cmd) for cmd in (entry.get("commands") or []) if isinstance(cmd, str)
                ]
                commands_clean, _ = sanitize_command_list(commands_raw, context=resource_id) if commands_raw else ([], [])
                record = ResourceRecord(
                    resource_id=resource_id,
                    label=label,
                    category=str(entry.get("category") or "block"),
                    aliases=[str(alias) for alias in (entry.get("aliases") or []) if isinstance(alias, str)],
                    tags=[str(tag) for tag in (entry.get("tags") or []) if isinstance(tag, str)],
                    available=self._safe_int(entry.get("available")),
                    commands=commands_clean,
                )
                resources.append(record)
        generated_at = payload.get("generated_at")
        if not isinstance(generated_at, str) or not generated_at.strip():
            generated_at = datetime.now(timezone.utc).isoformat()
        return ResourceSnapshot(resources=resources, generated_at=generated_at)