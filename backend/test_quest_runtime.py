"""Quest runtime regression tests for Phase 3 features.

Run with:

    cd backend
    python -m unittest test_quest_runtime.py
"""

from __future__ import annotations

import unittest

from app.core.quest.runtime import QuestRuntime
from app.core.story.story_loader import Level


def build_level(tasks):
    return Level(
        level_id="quest_test_level",
        title="Quest Test Level",
        level_type="story",
        tags=[],
        meta={},
        narrative={"text": ["Test narrative block."]},
        scene={},
        npcs=[],
        quests=[],
        tasks=tasks,
        navigation={},
        feedback={},
        ai_guidance={},
        bootstrap_patch={},
        tree=None,
        mood={},
    )


class QuestRuntimeTests(unittest.TestCase):
    def setUp(self):
        tasks = [
            {
                "id": "kill_goat",
                "type": "kill",
                "target": {"name": "goat"},
                "count": 2,
                "reward": {"world_patch": {"mc": {"effect": "kill_reward"}}},
                "dialogue": {"on_complete": "你战胜了山羊。"},
                "issue_node": {
                    "title": "击败山羊",
                    "text": "消灭两只山羊来稳住你的情绪。",
                },
            },
            {
                "id": "talk_mentor",
                "type": "interact",
                "target": "mentor_awu",
                "reward": {"world_patch": {"mc": {"title": "和阿无谈话成功"}}},
                "dialogue": {"on_complete": "阿无点头回应。"},
                "issue_node": {
                    "title": "和阿无对话",
                    "text": "与阿无交流一次，分享你的情绪。",
                },
            },
        ]
        self.level = build_level(tasks)
        self.player = "quest_test_player"
        self.runtime = QuestRuntime()
        self.runtime.load_level_tasks(self.level, self.player)

    def test_multi_task_kill_and_summary_flow(self):
        issued = self.runtime.issue_tasks_on_beat(self.level, self.player, {"id": "beat_1"})
        self.assertIsNotNone(issued, "First task should issue on beat completion")
        snapshot = self.runtime.get_runtime_snapshot(self.player)
        self.assertEqual(snapshot["tasks"][0]["status"], "issued")

        match = self.runtime.record_event(
            self.player,
            {"type": "kill", "target_id": "GoAt"},
        )
        self.assertTrue(match and match.get("matched"), "First kill should match")
        self.assertEqual(match.get("remaining"), 1)

        completed = self.runtime.record_event(
            self.player,
            {"event_type": "kill", "target": "goat"},
        )
        self.assertTrue(completed and completed.get("completed"), "Second kill should complete task")

        issued_second = self.runtime.issue_tasks_on_beat(self.level, self.player, {"id": "beat_2"})
        self.assertIsNotNone(issued_second, "Second task should issue after kill task")

        talk_completed = self.runtime.record_event(
            self.player,
            {"type": "interact", "target_id": "mentor_awu"},
        )
        self.assertTrue(talk_completed and talk_completed.get("completed"), "Interact task should complete immediately")

        updates = self.runtime.check_completion(self.level, self.player)
        self.assertIsNotNone(updates, "Completion check should surface updates")
        self.assertTrue(updates.get("exit_ready"), "All tasks completed should trigger exit_ready")
        self.assertIn("summary", updates, "Completion should include summary node")
        self.assertIn("kill_goat", updates.get("completed_tasks", []))
        self.assertIn("talk_mentor", updates.get("completed_tasks", []))

        world_patch = updates.get("world_patch", {})
        mc_patch = world_patch.get("mc", {}) if isinstance(world_patch, dict) else {}
        self.assertEqual(mc_patch.get("effect"), "kill_reward", "Reward merge should retain first reward effect")
        self.assertEqual(mc_patch.get("title"), "和阿无谈话成功", "Reward merge should include second reward title")

        final_snapshot = self.runtime.get_runtime_snapshot(self.player)
        self.assertTrue(final_snapshot.get("exit_ready"), "Snapshot should mark exit readiness after summary")


if __name__ == "__main__":
    unittest.main()
