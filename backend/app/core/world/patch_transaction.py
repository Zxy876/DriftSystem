"""Patch transaction logging utilities for deterministic world updates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class PatchTransactionEntry:
    patch_id: str
    template_id: str
    step_id: str
    commands: List[str]
    undo_patch: Dict[str, object]
    status: str
    created_at: str
    metadata: Dict[str, object]

    def to_json(self) -> str:
        payload = {
            "patch_id": self.patch_id,
            "template_id": self.template_id,
            "step_id": self.step_id,
            "commands": list(self.commands),
            "undo_patch": self.undo_patch,
            "status": self.status,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
        return json.dumps(payload, ensure_ascii=False)


class PatchTransactionLog:
    """Append-only JSONL log recording applied world patches and undo information."""

    def __init__(self, root: Optional[Path] = None) -> None:
        base = root or Path(__file__).resolve().parents[3] / "data" / "patch_logs"
        base.mkdir(parents=True, exist_ok=True)
        self._path = base / "transactions.log"

    def record(
        self,
        *,
        patch_id: str,
        template_id: str,
        step_id: str,
        commands: Iterable[str],
        undo_patch: Optional[Dict[str, object]] = None,
        status: str = "pending",
        metadata: Optional[Dict[str, object]] = None,
    ) -> PatchTransactionEntry:
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = PatchTransactionEntry(
            patch_id=patch_id,
            template_id=template_id,
            step_id=step_id,
            commands=list(commands),
            undo_patch=undo_patch or {"commands": []},
            status=status,
            created_at=timestamp,
            metadata=metadata or {},
        )
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(entry.to_json())
            stream.write("\n")
        return entry

    def record_status_update(
        self,
        base_entry: PatchTransactionEntry,
        *,
        status: str,
        metadata: Optional[Dict[str, object]] = None,
    ) -> PatchTransactionEntry:
        merged_metadata = dict(base_entry.metadata)
        if metadata:
            merged_metadata.update(metadata)
        return self.record(
            patch_id=base_entry.patch_id,
            template_id=base_entry.template_id,
            step_id=base_entry.step_id,
            commands=base_entry.commands,
            undo_patch=base_entry.undo_patch,
            status=status,
            metadata=merged_metadata,
        )

    def load(self) -> List[PatchTransactionEntry]:
        entries: List[PatchTransactionEntry] = []
        if not self._path.exists():
            return entries
        for line in self._path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            entries.append(
                PatchTransactionEntry(
                    patch_id=str(payload.get("patch_id")),
                    template_id=str(payload.get("template_id")),
                    step_id=str(payload.get("step_id")),
                    commands=[str(cmd) for cmd in payload.get("commands", [])],
                    undo_patch=payload.get("undo_patch", {}),
                    status=str(payload.get("status")),
                    created_at=str(payload.get("created_at")),
                    metadata={str(k): v for k, v in (payload.get("metadata", {}) or {}).items()},
                )
            )
        return entries
