"""Persistence helpers for per-player narrative story state."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Optional

from .story_state import StoryState, StoryStateEnvelope


class StoryStateRepository:
    """Append-safe JSON storage for story state snapshots."""

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir
        self._lock = Lock()
        self._root.mkdir(parents=True, exist_ok=True)

    def load(self, player_id: str, scenario_id: str) -> Optional[StoryState]:
        path = self._path_for(player_id, scenario_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        try:
            envelope = StoryStateEnvelope.model_validate(raw)
        except Exception:
            # Fallback to bare StoryState for backwards compatibility.
            try:
                return StoryState.model_validate(raw)
            except Exception:
                return None
        return envelope.state

    def save(self, state: StoryState) -> None:
        path = self._path_for(state.player_id, state.scenario_id)
        payload = StoryStateEnvelope(state=state).model_dump(mode="json")
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _path_for(self, player_id: str, scenario_id: str) -> Path:
        safe_player = _sanitize_segment(player_id or "anonymous")
        safe_scenario = _sanitize_segment(scenario_id or "default")
        return self._root / safe_player / f"{safe_scenario}.json"


def _sanitize_segment(segment: str) -> str:
    return "".join(ch for ch in segment if ch.isalnum() or ch in {"-", "_", "."}) or "default"
