from fastapi.testclient import TestClient

from app.main import app
import app.core.story.story_engine as story_module
from app.core.ai import intent_engine
from app.core.hint.engine import HintEngine


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


def test_parse_intent_shared_mode_never_calls_llm(monkeypatch):
    player_id = "audit_intent_shared"
    engine = story_module.story_engine
    engine._ensure_player(player_id)
    engine.set_runtime_mode(player_id, engine.MODE_SHARED)

    def _raise_if_called(*args, **kwargs):
        raise RuntimeError("ai_parse_multi_should_not_be_called_in_shared_mode")

    monkeypatch.setattr(intent_engine, "ai_parse_multi", _raise_if_called)

    result = intent_engine.parse_intent(
        player_id=player_id,
        text="请在我面前放置 minecraft:amethyst_block",
        world_state={},
        story_engine=engine,
    )

    assert result["status"] == "ok"
    assert result["intents"]
    assert result["intents"][0]["type"] == "CREATE_BLOCK"


def test_hint_engine_fail_open_when_model_unavailable(monkeypatch):
    class _TreeStub:
        def export_state(self):
            return {"current": {"id": "n1", "title": "stub"}}

    def _raise(*args, **kwargs):
        raise RuntimeError("upstream_unavailable")

    monkeypatch.setattr("app.core.hint.engine.call_deepseek", _raise)
    engine = HintEngine(_TreeStub())

    resp = engine.get_hint("给我一点提示")
    result = resp.get("result") or {}

    assert resp.get("current_node", {}).get("id") == "n1"
    assert result.get("action") is None
    assert result.get("fallback") is True


def test_personal_mode_llm_exception_does_not_block_advance(monkeypatch):
    engine = story_module.story_engine
    player_id = "audit_personal_fail_open"

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated_upstream_failure")

    monkeypatch.setattr(story_module, "deepseek_decide", _raise)

    engine._ensure_player(player_id)
    engine.set_runtime_mode(player_id, engine.MODE_PERSONAL)
    engine._ensure_free_mode_level(player_id)
    engine.players[player_id]["story_prebuffer"] = []

    option, node, patch = engine.advance(
        player_id,
        {"variables": {"x": 0, "y": 64, "z": 0}},
        {"say": "继续剧情"},
    )

    assert option is None
    assert isinstance(node, dict)
    assert "降级叙事" in node.get("title", "")
    assert isinstance(patch, dict)
