from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.ai.intent_engine import parse_intent


class _DummyMinimap:
    def to_dict(self, player_id: str):
        return {"current_level": "flagship_01", "player_id": player_id}


class _DummyStoryEngine:
    minimap = _DummyMinimap()


class IntentSceneThemeMappingTest(unittest.TestCase):
    def test_create_story_prefix_maps_scene_theme(self):
        with patch("app.core.ai.intent_engine.ai_parse_multi", return_value=None):
            result = parse_intent(
                player_id="vivn",
                text="创建剧情 大风吹",
                world_state={},
                story_engine=_DummyStoryEngine(),
            )

        intent = result["intents"][0]
        self.assertEqual(intent["type"], "CREATE_STORY")
        self.assertEqual(intent.get("scene_theme"), "大风吹")
        self.assertEqual(intent.get("raw_text"), "创建剧情 大风吹")

    def test_create_level_prefix_maps_scene_theme(self):
        with patch("app.core.ai.intent_engine.ai_parse_multi", return_value=None):
            result = parse_intent(
                player_id="vivn",
                text="创建关卡 暴风雨营地",
                world_state={},
                story_engine=_DummyStoryEngine(),
            )

        intent = result["intents"][0]
        self.assertEqual(intent["type"], "CREATE_STORY")
        self.assertEqual(intent.get("scene_theme"), "暴风雨营地")

    def test_natural_scene_sentence_maps_scene_theme(self):
        with patch("app.core.ai.intent_engine.ai_parse_multi", return_value=None):
            result = parse_intent(
                player_id="vivn",
                text="我要一个大风吹的场景",
                world_state={},
                story_engine=_DummyStoryEngine(),
            )

        intent = result["intents"][0]
        self.assertEqual(intent["type"], "CREATE_STORY")
        self.assertEqual(intent.get("scene_theme"), "大风吹")

    def test_create_story_with_location_maps_scene_hint(self):
        with patch("app.core.ai.intent_engine.ai_parse_multi", return_value=None):
            result = parse_intent(
                player_id="vivn",
                text="创建剧情 大风吹 在森林里",
                world_state={},
                story_engine=_DummyStoryEngine(),
            )

        intent = result["intents"][0]
        self.assertEqual(intent["type"], "CREATE_STORY")
        self.assertEqual(intent.get("scene_theme"), "大风吹")
        self.assertEqual(intent.get("scene_hint"), "森林")

    def test_create_story_with_coast_hint_maps_scene_hint(self):
        with patch("app.core.ai.intent_engine.ai_parse_multi", return_value=None):
            result = parse_intent(
                player_id="vivn",
                text="创建剧情 暴风雨 在海边",
                world_state={},
                story_engine=_DummyStoryEngine(),
            )

        intent = result["intents"][0]
        self.assertEqual(intent["type"], "CREATE_STORY")
        self.assertEqual(intent.get("scene_theme"), "暴风雨")
        self.assertEqual(intent.get("scene_hint"), "海边")

    def test_ai_theme_field_is_mapped_to_scene_theme(self):
        ai_result = [{"type": "CREATE_STORY", "raw_text": "创建剧情 大风吹", "theme": "大风吹"}]
        with patch("app.core.ai.intent_engine.ai_parse_multi", return_value=ai_result):
            result = parse_intent(
                player_id="vivn",
                text="创建剧情 大风吹",
                world_state={},
                story_engine=_DummyStoryEngine(),
            )

        intent = result["intents"][0]
        self.assertEqual(intent["type"], "CREATE_STORY")
        self.assertEqual(intent.get("scene_theme"), "大风吹")
        self.assertNotIn("theme", intent)

    def test_ai_hint_field_is_mapped_to_scene_hint(self):
        ai_result = [
            {
                "type": "CREATE_STORY",
                "raw_text": "创建剧情 大风吹 在森林里",
                "theme": "大风吹",
                "hint": "森林",
            }
        ]
        with patch("app.core.ai.intent_engine.ai_parse_multi", return_value=ai_result):
            result = parse_intent(
                player_id="vivn",
                text="创建剧情 大风吹 在森林里",
                world_state={},
                story_engine=_DummyStoryEngine(),
            )

        intent = result["intents"][0]
        self.assertEqual(intent["type"], "CREATE_STORY")
        self.assertEqual(intent.get("scene_theme"), "大风吹")
        self.assertEqual(intent.get("scene_hint"), "森林")
        self.assertNotIn("hint", intent)


if __name__ == "__main__":
    unittest.main()
