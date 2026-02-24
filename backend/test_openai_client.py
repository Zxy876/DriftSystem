"""Tests for OpenAIClient (Issue 6.1)."""
import logging

import pytest

from app.integration.openai_client import OpenAIClient


def test_dry_run_default(caplog):
    caplog.set_level(logging.INFO)
    client = OpenAIClient(api_key=None, dry_run=True)
    resp = client.chat("hello")
    assert resp["status"] == "dry-run"
    assert "openai_dry_run" in {r.message for r in caplog.records}


def test_enabled_requires_key(monkeypatch):
    monkeypatch.setenv("MODEL_CALLS_ENABLED", "1")
    client = OpenAIClient(api_key=None, dry_run=False)
    with pytest.raises(RuntimeError):
        client.chat("hello")


def test_enabled_success(monkeypatch, caplog):
    monkeypatch.setenv("MODEL_CALLS_ENABLED", "1")
    caplog.set_level(logging.INFO)
    client = OpenAIClient(api_key="test-key", dry_run=False)
    resp = client.chat("hello", model="gpt-test")
    assert resp["status"] == "ok"
    assert resp["model"] == "gpt-test"
    assert any(r.message == "openai_call" for r in caplog.records)
