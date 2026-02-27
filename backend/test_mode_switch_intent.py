from __future__ import annotations

from app.core.ai import intent_engine


class _DummyMiniMap:
    def to_dict(self, _player_id: str):
        return {"ok": True}


class _DummyStoryEngine:
    MODE_SHARED = "shared"
    MODE_PERSONAL = "personal"

    def __init__(self, mode: str):
        self._mode = mode
        self.minimap = _DummyMiniMap()

    def get_runtime_mode(self, _player_id: str):
        return self._mode


def test_fallback_intent_detects_enter_personal():
    intents = intent_engine.fallback_intents("进入创作空间")
    assert intents
    assert intents[0]["type"] == "MODE_SWITCH"
    assert intents[0]["mode_target"] == "personal"


def test_fallback_intent_detects_exit_to_shared():
    intents = intent_engine.fallback_intents("回到共享空间")
    assert intents
    assert intents[0]["type"] == "MODE_SWITCH"
    assert intents[0]["mode_target"] == "shared"


def test_parse_intent_in_shared_mode_returns_mode_switch_without_llm(monkeypatch):
    def _forbidden_ai(*_args, **_kwargs):
        raise AssertionError("ai_parse_multi should not run in shared mode")

    monkeypatch.setattr(intent_engine, "ai_parse_multi", _forbidden_ai)

    result = intent_engine.parse_intent(
        player_id="player_a",
        text="开始创作",
        world_state={},
        story_engine=_DummyStoryEngine(mode="shared"),
    )

    assert result["status"] == "ok"
    assert result["intents"]
    assert result["intents"][0]["type"] == "MODE_SWITCH"
    assert result["intents"][0]["mode_target"] == "personal"


def test_fallback_intent_detects_story_import():
    intents = intent_engine.fallback_intents("请把这段剧情导入成一个新关卡")
    assert intents
    assert intents[0]["type"] == "CREATE_STORY"
    assert intents[0]["raw_text"] == "请把这段剧情导入成一个新关卡"


def test_parse_intent_in_shared_mode_detects_story_import_without_llm(monkeypatch):
    def _forbidden_ai(*_args, **_kwargs):
        raise AssertionError("ai_parse_multi should not run for explicit story import")

    monkeypatch.setattr(intent_engine, "ai_parse_multi", _forbidden_ai)

    result = intent_engine.parse_intent(
        player_id="player_b",
        text="导入这段剧情并生成关卡",
        world_state={},
        story_engine=_DummyStoryEngine(mode="shared"),
    )

    assert result["status"] == "ok"
    assert result["intents"]
    assert result["intents"][0]["type"] == "CREATE_STORY"


def test_parse_intent_in_shared_mode_detects_scene_import_wording_without_llm(monkeypatch):
    def _forbidden_ai(*_args, **_kwargs):
        raise AssertionError("ai_parse_multi should not run for explicit scene import")

    monkeypatch.setattr(intent_engine, "ai_parse_multi", _forbidden_ai)

    result = intent_engine.parse_intent(
        player_id="player_c",
        text="导入一个情景；三个小孩在跪着",
        world_state={},
        story_engine=_DummyStoryEngine(mode="shared"),
    )

    assert result["status"] == "ok"
    assert result["intents"]
    assert result["intents"][0]["type"] == "CREATE_STORY"
