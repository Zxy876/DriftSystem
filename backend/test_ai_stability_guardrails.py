from fastapi.testclient import TestClient

from app.main import app
import app.core.story.story_engine as story_module


def test_quota_status_endpoint_shape():
    client = TestClient(app)
    resp = client.get("/ai/quota-status")
    assert resp.status_code == 200
    payload = resp.json()
    for key in (
        "provider",
        "model",
        "last_error",
        "rate_limit_hits",
        "timeout_count",
        "fallback_count",
    ):
        assert key in payload


def test_shared_mode_does_not_call_llm(monkeypatch):
    engine = story_module.story_engine
    player_id = "audit_shared_user"

    def _raise_if_called(*args, **kwargs):
        raise RuntimeError("deepseek_should_not_be_called_in_shared_mode")

    monkeypatch.setattr(story_module, "deepseek_decide", _raise_if_called)

    engine._ensure_player(player_id)
    engine.set_runtime_mode(player_id, engine.MODE_SHARED)

    option, node, patch = engine.advance(
        player_id,
        {"variables": {"x": 0, "y": 64, "z": 0}},
        {"say": "hello"},
    )

    assert option is None
    assert isinstance(node, dict)
    assert "Shared" in node.get("title", "")
    assert isinstance(patch, dict)


def test_story_prebuffer_generates_three_beats(monkeypatch):
    engine = story_module.story_engine
    player_id = "audit_prebuffer_user"

    calls = {"count": 0}

    def _fake_deepseek_decide(context, messages):
        calls["count"] += 1
        idx = calls["count"]
        return {
            "option": idx,
            "node": {"title": f"beat-{idx}", "text": "ok"},
            "world_patch": {"variables": {"beat": idx}, "mc": {}},
        }

    monkeypatch.setattr(story_module, "deepseek_decide", _fake_deepseek_decide)

    engine._ensure_player(player_id)
    engine.set_runtime_mode(player_id, engine.MODE_PERSONAL)
    engine._ensure_free_mode_level(player_id)

    generated = engine.prebuffer_story_beats(player_id, count=3)
    cache = engine.players[player_id].get("story_prebuffer", [])

    assert generated >= 3
    assert len(cache) >= 3
