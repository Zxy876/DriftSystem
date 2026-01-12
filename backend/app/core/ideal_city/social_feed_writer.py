"""Utilities for Forge to publish social feedback artefacts."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

_VALID_CATEGORIES = {"praise", "concern", "controversy", "regulation_proposal"}


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat(value: datetime) -> str:
    return _ensure_utc(value).isoformat()


def _load_existing_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry_id = str(payload.get("entry_id") or "").strip()
                if entry_id:
                    ids.add(entry_id)
    except OSError:
        return ids
    return ids


def _atomic_write(path: Path, payload: dict) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


class SocialFeedWriter:
    """File-backed helper to publish Forge social feedback entries."""

    def __init__(self, protocol_root: Path) -> None:
        self._root = Path(protocol_root) / "cityphone" / "social-feed"
        self._events_file = self._root / "events.jsonl"
        self._metrics_file = self._root / "metrics.json"
        self._lock = threading.Lock()
        self._root.mkdir(parents=True, exist_ok=True)

    def append_event(
        self,
        *,
        entry_id: str,
        category: str,
        title: str,
        body: str,
        issued_at: datetime,
        stage: Optional[int] = None,
        trust_delta: Optional[float] = None,
        stress_delta: Optional[float] = None,
        tags: Optional[Iterable[str]] = None,
        allow_duplicate: bool = False,
    ) -> bool:
        category_key = category.strip().lower()
        if category_key not in _VALID_CATEGORIES:
            raise ValueError(f"Unsupported social feedback category: {category}")
        payload: dict = {
            "entry_id": entry_id,
            "category": category_key,
            "title": title,
            "body": body,
            "issued_at": _isoformat(issued_at),
        }
        if stage is not None:
            payload["stage"] = int(stage)
        if trust_delta is not None:
            payload["trust_delta"] = float(trust_delta)
        if stress_delta is not None:
            payload["stress_delta"] = float(stress_delta)
        if tags:
            payload["tags"] = [str(tag) for tag in tags if str(tag).strip()]

        with self._lock:
            if not allow_duplicate and entry_id in _load_existing_ids(self._events_file):
                return False
            self._events_file.parent.mkdir(parents=True, exist_ok=True)
            with self._events_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        return True

    def set_metrics(
        self,
        *,
        trust_index: float,
        stress_index: float,
        updated_at: Optional[datetime] = None,
    ) -> None:
        snapshot = {
            "trust_index": float(trust_index),
            "stress_index": float(stress_index),
        }
        if updated_at is not None:
            snapshot["updated_at"] = _isoformat(updated_at)
        else:
            snapshot["updated_at"] = _isoformat(datetime.now(timezone.utc))
        with self._lock:
            self._metrics_file.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(self._metrics_file, snapshot)

    def clear_events(self) -> None:
        with self._lock:
            if self._events_file.exists():
                self._events_file.unlink()

    def clear_metrics(self) -> None:
        with self._lock:
            if self._metrics_file.exists():
                self._metrics_file.unlink()
