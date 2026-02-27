from __future__ import annotations

import json
from pathlib import Path

from app.api import story_api
from app.api.story_api import InjectPayload


def test_story_inject_returns_level_id_and_writes_level(monkeypatch, tmp_path):
    monkeypatch.setattr(story_api, "DATA_DIR", str(tmp_path))

    def _fake_realize_scene(_payload):
        return {"status": "ok", "execution_mode": "dry_run"}

    monkeypatch.setattr(story_api, "realize_scene", _fake_realize_scene)

    import app.core.ai.deepseek_agent as deepseek_agent

    def _fake_call_deepseek(**_kwargs):
        return {"response": "{}"}

    monkeypatch.setattr(deepseek_agent, "call_deepseek", _fake_call_deepseek)

    payload = InjectPayload(
        level_id="custom_demo",
        title="测试导入",
        text="导入剧情：在湖边建一个灯塔并安排向导NPC",
        player_id="tester",
        execute_confirm=False,
    )

    result = story_api.api_story_inject(payload)

    assert result["status"] == "ok"
    assert result["level_id"] == "flagship_custom_demo"

    target_file = Path(result["file"])
    assert target_file.exists()
    assert target_file.name == "flagship_custom_demo.json"

    with open(result["file"], "r", encoding="utf-8") as fp:
        level_data = json.load(fp)
    mc = level_data["bootstrap_patch"]["mc"]
    assert "spawn_multi" in mc
    assert "build" in mc
    assert mc["spawn_multi"][0]["name"] in {"爷爷", "回忆引导者"}


def test_story_inject_maps_ai_scene_to_plugin_supported_ops(monkeypatch, tmp_path):
    monkeypatch.setattr(story_api, "DATA_DIR", str(tmp_path))

    def _fake_realize_scene(_payload):
        return {"status": "ok", "execution_mode": "dry_run"}

    monkeypatch.setattr(story_api, "realize_scene", _fake_realize_scene)

    import app.core.ai.deepseek_agent as deepseek_agent

    def _fake_call_deepseek(**_kwargs):
        data = {
            "spawn": {"x": 8, "y": 72, "z": -3},
            "npcs": [
                {"type": "villager", "name": "向导", "x": 10, "y": 72, "z": -3, "dialog": "跟我来"}
            ],
            "blocks": [
                {"type": "stone", "x": 8, "y": 71, "z": -3},
                {"type": "minecraft:glass", "x": 8, "y": 72, "z": -2},
            ],
            "time": "night",
            "weather": "clear",
        }
        return {"response": f"```json\n{json.dumps(data, ensure_ascii=False)}\n```"}

    monkeypatch.setattr(deepseek_agent, "call_deepseek", _fake_call_deepseek)

    payload = InjectPayload(
        level_id="custom_scene_ops",
        title="映射测试",
        text="导入剧情：夜晚集市与向导",
        player_id="tester",
        execute_confirm=False,
    )

    result = story_api.api_story_inject(payload)

    with open(result["file"], "r", encoding="utf-8") as fp:
        level_data = json.load(fp)

    mc = level_data["bootstrap_patch"]["mc"]
    assert mc["spawn"] == {"x": 8, "y": 72, "z": -3}
    assert mc["time"] == "night"
    assert mc["weather"] == "clear"
    assert "spawn_multi" in mc
    assert mc["spawn_multi"][0]["name"] == "向导"
    assert "commands" in mc
    assert "setblock 8 71 -3 minecraft:stone" in mc["commands"]
    assert "setblock 8 72 -2 minecraft:glass" in mc["commands"]


def test_story_inject_ai_exception_uses_rich_memory_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(story_api, "DATA_DIR", str(tmp_path))

    def _fake_realize_scene(_payload):
        return {"status": "ok", "execution_mode": "dry_run"}

    monkeypatch.setattr(story_api, "realize_scene", _fake_realize_scene)

    import app.core.ai.deepseek_agent as deepseek_agent

    def _fake_call_deepseek(**_kwargs):
        raise RuntimeError("upstream timeout")

    monkeypatch.setattr(deepseek_agent, "call_deepseek", _fake_call_deepseek)

    payload = InjectPayload(
        level_id="custom_ai_error",
        title="异常兜底测试",
        text="导入剧情：我和爷爷在院子里修风筝",
        player_id="tester",
        execute_confirm=False,
    )

    result = story_api.api_story_inject(payload)

    with open(result["file"], "r", encoding="utf-8") as fp:
        level_data = json.load(fp)

    mc = level_data["bootstrap_patch"]["mc"]
    assert "spawn_multi" in mc and len(mc["spawn_multi"]) >= 1
    assert "commands" in mc and len(mc["commands"]) >= 1
    assert "title" in mc
