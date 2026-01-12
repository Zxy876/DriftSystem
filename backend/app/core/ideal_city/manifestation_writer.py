"""Filesystem delivery for Manifestation Intent protocol payloads."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, Optional
from uuid import uuid4

from .manifestation_intent import ManifestationIntent


class ManifestationIntentWriter:
    """Persist intents to the protocol delivery directories with atomic writes."""

    def __init__(self, protocol_root: Path, *, enable_audit: bool = True) -> None:
        self._city_intents_root = protocol_root / "city-intents"
        self._pending_dir = self._city_intents_root / "pending"
        self._processing_dir = self._city_intents_root / "processing"
        self._processed_dir = self._city_intents_root / "processed"
        self._failed_dir = self._city_intents_root / "failed"
        self._audit_file = self._city_intents_root / "intent_audit.jsonl" if enable_audit else None

        self._pending_dir.mkdir(parents=True, exist_ok=True)
        self._processing_dir.mkdir(parents=True, exist_ok=True)
        self._processed_dir.mkdir(parents=True, exist_ok=True)
        self._failed_dir.mkdir(parents=True, exist_ok=True)
        if self._audit_file is not None:
            self._audit_file.parent.mkdir(parents=True, exist_ok=True)

    @property
    def pending_directory(self) -> Path:
        return self._pending_dir

    def write_intent(self, intent: ManifestationIntent, *, player_id: str, spec_id: Optional[str] = None) -> Path:
        if not player_id:
            raise ValueError("player_id is required for intent publication")

        intent_payload = intent.model_dump(mode="json")
        if spec_id:
            intent_payload.setdefault("metadata", {})["source_spec_id"] = spec_id

        envelope: Dict[str, object] = {
            "player_id": player_id,
            "intent": intent_payload,
        }

        filename = f"{intent.intent_id}.json"
        final_path = self._pending_dir / filename
        temp_path = final_path.parent / f".{intent.intent_id}.{uuid4().hex}.tmp"

        self._write_atomic(temp_path, final_path, envelope)

        if self._audit_file is not None:
            audit_payload = dict(envelope)
            audit_payload.setdefault("metadata", {})
            audit_payload["metadata"]["storage"] = "city-intents/pending"
            self._append_json(self._audit_file, audit_payload)

        return final_path

    def load_pending(self) -> Iterable[ManifestationIntent]:
        for path in sorted(self._pending_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            intent_payload = payload.get("intent") if isinstance(payload, dict) else None
            if not isinstance(intent_payload, dict):
                continue
            try:
                intent = ManifestationIntent.model_validate(intent_payload)
            except Exception:
                continue
            yield intent

    def _write_atomic(self, temp_path: Path, final_path: Path, payload: Dict[str, object]) -> None:
        # Write temp file then rename so Forge never sees partial payloads.
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, final_path)

    def _append_json(self, path: Path, payload: Dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write("\n")
