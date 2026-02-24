"""Tests for ActorMemoryStore (Issue 4.1)."""
from pathlib import Path

import pytest

from app.actors.memory_store import ActorMemoryStore, STAGES


def test_invalid_stage(tmp_path: Path) -> None:
    store = ActorMemoryStore(tmp_path / "mem.db")
    with pytest.raises(ValueError):
        store.save_memory("actor1", "UNKNOWN", {}, session_id=None)
    with pytest.raises(ValueError):
        store.load_memory("actor1", "UNKNOWN")


def test_save_and_load_long_term(tmp_path: Path) -> None:
    store = ActorMemoryStore(tmp_path / "mem.db")
    store.save_memory("actor1", "IMPORT", {"mood": "calm"})
    data = store.load_memory("actor1", "IMPORT")
    assert data["mood"] == "calm"


def test_rehearse_does_not_write_long_term(tmp_path: Path) -> None:
    store = ActorMemoryStore(tmp_path / "mem.db")
    store.save_memory("actor1", "IMPORT", {"seed": "base"})
    store.save_memory("actor1", "REHEARSE", {"temp": "scene-only"}, session_id="sess1")

    # long_term should remain unchanged
    data = store.load_memory("actor1", "TAKE")
    assert data.get("temp") is None
    assert data["seed"] == "base"

    # scene data accessible with session_id
    scene_data = store.load_memory("actor1", "REHEARSE", session_id="sess1")
    assert scene_data["temp"] == "scene-only"


def test_take_updates_long_term_and_scene(tmp_path: Path) -> None:
    store = ActorMemoryStore(tmp_path / "mem.db")
    store.save_memory("actor1", "TAKE", {"memory": {"foo": 1}}, session_id="sess2")
    data = store.load_memory("actor1", "TAKE")
    assert data["memory"] == {"foo": 1}

    scene_data = store.load_memory("actor1", "TAKE", session_id="sess2")
    assert scene_data["memory"] == {"foo": 1}


def test_list_sessions(tmp_path: Path) -> None:
    store = ActorMemoryStore(tmp_path / "mem.db")
    store.save_memory("actor1", "REHEARSE", {"temp": 1}, session_id="s1")
    store.save_memory("actor1", "TAKE", {"final": 2}, session_id="s2")
    sessions = list(store.list_sessions())
    assert set(sessions) == {"s1", "s2"}
