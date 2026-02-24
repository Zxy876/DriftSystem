"""Tests for Prompt Builder (Issue 4.2)."""
import os
from pathlib import Path

import pytest

from app.actors.memory_store import ActorMemoryStore
from app.actors.prompt_builder import build_prompt


@pytest.fixture
def store(tmp_path: Path) -> ActorMemoryStore:
    return ActorMemoryStore(tmp_path / "mem.db")


def test_invalid_stage(store: ActorMemoryStore) -> None:
    with pytest.raises(ValueError):
        build_prompt("actor1", "UNKNOWN", {}, store=store)


def test_deterministic_prompt_when_model_disabled(store: ActorMemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_CALLS_ENABLED", raising=False)
    store.save_memory("actor1", "IMPORT", {"seed": "calm"})
    prompt = build_prompt(
        "actor1",
        "IMPORT",
        {"beat_id": "b1", "description": "greet"},
        store=store,
    )
    assert "mode=dry" in prompt
    assert "seed" in prompt
    assert "greet" in prompt


def test_prompt_respects_session_memory(store: ActorMemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_CALLS_ENABLED", "1")
    store.save_memory("actor1", "IMPORT", {"seed": "base"})
    store.save_memory("actor1", "REHEARSE", {"scene": "temp"}, session_id="sess1")

    prompt = build_prompt(
        "actor1",
        "REHEARSE",
        {"beat_id": "b2", "description": "practice"},
        store=store,
        session_id="sess1",
    )
    assert "mode=llm" in prompt
    assert "scene" in prompt
    assert "practice" in prompt
