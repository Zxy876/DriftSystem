from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.quest.quest_state_store import QuestStateStore
from app.core.quest.runtime import QuestRuntime
from app.core.story.story_loader import Level


class QuestStatePersistenceTest(unittest.TestCase):
    @staticmethod
    def _build_level(level_id: str, tasks: list[dict]) -> Level:
        level = Level(
            level_id=level_id,
            title=f"{level_id} title",
            text=[],
            tags=[],
            mood={},
            choices=[],
            meta={},
            npcs=[],
            bootstrap_patch={},
        )
        setattr(level, "tasks", tasks)
        return level

    def test_quest_state_store_roundtrip(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "quest_state.db"
            store = QuestStateStore(str(db_path))

            payload = {
                "issued_index": 0,
                "completed_count": 1,
                "summary_emitted": False,
                "tasks": [
                    {
                        "id": "collect_wood",
                        "type": "collect",
                        "status": "issued",
                        "progress": 1,
                        "count": 2,
                    }
                ],
            }

            store.save_state("vivn", "flagship_quest_test", payload)
            restored = store.load_state("vivn", "flagship_quest_test")

            self.assertIsInstance(restored, dict)
            self.assertEqual(restored.get("issued_index"), 0)
            self.assertEqual(restored.get("completed_count"), 1)
            self.assertEqual(restored.get("tasks", [])[0].get("id"), "collect_wood")

    def test_runtime_restores_issued_progress_after_recreation(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "quest_state.db"
            store = QuestStateStore(str(db_path))

            level = self._build_level(
                "flagship_quest_resume",
                [
                    {
                        "id": "collect_wood",
                        "type": "collect",
                        "target": "wood",
                        "title": "Collect Wood",
                        "count": 2,
                    }
                ],
            )

            runtime_first = QuestRuntime()
            runtime_first._quest_state_store = store
            runtime_first.load_level_tasks(level, "vivn")
            runtime_first.issue_tasks_on_beat(level, "vivn", {"id": "beat_01"})
            runtime_first.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "collect",
                    "target": "wood",
                    "payload": {
                        "resource": "wood",
                        "amount": 1,
                    },
                },
            )

            snapshot_first = runtime_first.get_runtime_snapshot("vivn")
            self.assertEqual(snapshot_first["tasks"][0]["status"], "issued")
            self.assertEqual(snapshot_first["tasks"][0]["progress"], 1)

            runtime_second = QuestRuntime()
            runtime_second._quest_state_store = QuestStateStore(str(db_path))
            runtime_second.load_level_tasks(level, "vivn")

            snapshot_second = runtime_second.get_runtime_snapshot("vivn")
            self.assertEqual(snapshot_second["tasks"][0]["status"], "issued")
            self.assertEqual(snapshot_second["tasks"][0]["progress"], 1)
            self.assertEqual(snapshot_second["tasks"][0]["count"], 2)

    def test_runtime_restores_rewarded_and_summary_flags(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "quest_state.db"
            store = QuestStateStore(str(db_path))

            level = self._build_level(
                "flagship_quest_complete",
                [
                    {
                        "id": "collect_wood_once",
                        "type": "collect",
                        "target": "wood",
                        "title": "Collect One Wood",
                        "count": 1,
                        "reward": {
                            "world_patch": {
                                "mc": {
                                    "tell": "Reward granted",
                                }
                            }
                        },
                    }
                ],
            )

            runtime_first = QuestRuntime()
            runtime_first._quest_state_store = store
            runtime_first.load_level_tasks(level, "vivn")
            runtime_first.issue_tasks_on_beat(level, "vivn", {"id": "beat_01"})
            runtime_first.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "collect",
                    "target": "wood",
                    "payload": {
                        "resource": "wood",
                        "amount": 1,
                    },
                },
            )

            first_completion = runtime_first.check_completion(level, "vivn")
            self.assertIsNotNone(first_completion)
            self.assertTrue(first_completion.get("nodes"))

            runtime_first.exit_level("vivn")

            runtime_second = QuestRuntime()
            runtime_second._quest_state_store = QuestStateStore(str(db_path))
            runtime_second.load_level_tasks(level, "vivn")

            snapshot_second = runtime_second.get_runtime_snapshot("vivn")
            self.assertTrue(snapshot_second.get("exit_ready"))
            self.assertEqual(snapshot_second["tasks"][0]["status"], "completed")

            second_completion = runtime_second.check_completion(level, "vivn")
            self.assertIsNone(second_completion)


if __name__ == "__main__":
    unittest.main()
