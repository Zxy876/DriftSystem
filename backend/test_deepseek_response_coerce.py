from __future__ import annotations

import app.core.ai.deepseek_agent as agent


def test_coerce_ai_result_from_plain_text():
    result = agent._coerce_ai_result("这是普通文本，不是json")
    assert isinstance(result, dict)
    assert isinstance(result.get("node"), dict)
    assert result["node"]["title"] == "创造之城 · 回声"
    assert "普通文本" in result["node"]["text"]


def test_coerce_ai_result_from_fenced_json():
    payload = """```json
{"option": 1, "node": {"title": "t", "text": "x"}, "world_patch": {"mc": {}}}
```"""
    result = agent._coerce_ai_result(payload)
    assert result.get("option") == 1
    assert result.get("node", {}).get("title") == "t"


def test_circuit_allows_periodic_probe(monkeypatch):
    monkeypatch.setattr(agent, "AI_DISABLED", False)
    monkeypatch.setattr(agent, "AI_CIRCUIT_PROBE_SECONDS", 5.0)

    now = 100.0
    agent._failure_state["open_until"] = now + 20.0
    agent._failure_state["last_probe"] = 0.0

    opened1, reason1 = agent._circuit_status(now=now)
    opened2, reason2 = agent._circuit_status(now=now + 1.0)

    assert opened1 is False
    assert reason1 == "circuit_probe"
    assert opened2 is True
    assert reason2 == "circuit_open"
