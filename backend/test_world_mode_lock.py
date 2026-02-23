from __future__ import annotations

from app.api import world_api
from app.api.world_api import ApplyInput, EndStoryRequest, EnterStoryRequest, WorldAction


class _DummyWorldEngine:
    def apply(self, _act):
        return {"variables": {"x": 0, "y": 64, "z": 0}, "entities": {}}


class _DummyStoryEngine:
    MODE_SHARED = "shared"
    MODE_PERSONAL = "personal"
    MODE_RETURN = "return"

    def __init__(self):
        self.players = {}

    def get_runtime_mode(self, player_id):
        return self.players.get(player_id, {}).get("runtime_mode", self.MODE_SHARED)

    def set_runtime_mode(self, player_id, mode):
        state = self.players.setdefault(player_id, {})
        state["runtime_mode"] = mode
        return mode

    def get_next_level_id(self, *_args, **_kwargs):
        return "flagship_tutorial"

    def load_level_for_player(self, player_id, level_id):
        state = self.players.setdefault(player_id, {})
        state["level"] = type("_L", (), {"level_id": level_id})()
        return {"mc": {"tell": f"loaded {level_id}"}}

    def exit_level_with_cleanup(self, player_id, _level):
        state = self.players.setdefault(player_id, {})
        state["level"] = None
        return {"mc": {"tell": "cleanup"}}

    def graph(self):  # pragma: no cover
        return None


class _DummyQuestRuntime:
    def exit_level(self, _player_id):
        return None


def test_world_apply_say_is_blocked_in_shared_mode(monkeypatch):
    dummy_story = _DummyStoryEngine()
    monkeypatch.setattr(world_api, "story_engine", dummy_story)
    monkeypatch.setattr(world_api, "world_engine", _DummyWorldEngine())

    def _forbidden_parse(*_args, **_kwargs):
        raise AssertionError("parse_intent should not run in shared mode")

    monkeypatch.setattr(world_api, "parse_intent", _forbidden_parse)

    response = world_api.apply_action(
        ApplyInput(player_id="player_shared", action=WorldAction(say="你好"))
    )

    assert response.status == "ok"
    assert isinstance(response.story_node, dict)
    assert response.story_node.get("title") == "Mode Locked"


def test_story_start_and_end_switch_runtime_mode(monkeypatch):
    dummy_story = _DummyStoryEngine()
    monkeypatch.setattr(world_api, "story_engine", dummy_story)
    monkeypatch.setattr(world_api, "quest_runtime", _DummyQuestRuntime())

    start_resp = world_api.story_start(EnterStoryRequest(player_id="p1", level_id="flagship_01"))
    assert start_resp["status"] == "ok"
    assert start_resp["mode"] == "personal"

    end_resp = world_api.story_end(EndStoryRequest(player_id="p1", level_id="flagship_01"))
    assert end_resp["status"] == "ok"
    assert end_resp["mode"] == "shared"
