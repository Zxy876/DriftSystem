from __future__ import annotations

import app.core.ai.deepseek_agent as agent


def _reset_agent_state(monkeypatch):
    monkeypatch.setattr(agent, "API_KEY", "test-key")
    monkeypatch.setattr(agent, "MIN_INTERVAL", 10.0)
    agent._LAST_CALL_TS.clear()
    agent._LAST_DECISION.clear()
    agent._LAST_USER_SIGNATURE.clear()


def test_prebuffer_bypasses_throttle(monkeypatch):
    _reset_agent_state(monkeypatch)

    calls = {"n": 0}

    def _fake_call(payload, *_args, **_kwargs):
        calls["n"] += 1
        return {
            "option": calls["n"],
            "node": {"title": f"beat-{calls['n']}", "text": "ok"},
            "world_patch": {"variables": {}, "mc": {}},
        }

    monkeypatch.setattr(agent, "_call_deepseek_api", _fake_call)

    context = {
        "player_id": "p_prebuffer",
        "story_prebuffer": True,
        "player_action": {"type": "prebuffer"},
    }

    r1 = agent.deepseek_decide(context, [{"role": "assistant", "content": "a"}])
    r2 = agent.deepseek_decide(context, [{"role": "assistant", "content": "b"}])

    assert calls["n"] == 2
    assert r1["node"]["title"] != r2["node"]["title"]


def test_duplicate_user_input_is_throttled(monkeypatch):
    _reset_agent_state(monkeypatch)

    calls = {"n": 0}

    def _fake_call(payload, *_args, **_kwargs):
        calls["n"] += 1
        return {
            "option": calls["n"],
            "node": {"title": f"live-{calls['n']}", "text": "ok"},
            "world_patch": {"variables": {}, "mc": {}},
        }

    monkeypatch.setattr(agent, "_call_deepseek_api", _fake_call)

    context = {
        "player_id": "p_live",
        "player_action": {"type": "say"},
    }
    history = [{"role": "user", "content": "继续"}]

    r1 = agent.deepseek_decide(context, history)
    r2 = agent.deepseek_decide(context, history)

    assert calls["n"] == 1
    assert r1["node"]["title"] == r2["node"]["title"]
