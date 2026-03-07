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

from app.core.quest.inventory_store import InventoryStore
from app.core.quest.quest_state_store import QuestStateStore
from app.core.quest.runtime import QuestRuntime
from app.core.story.story_loader import Level


class P4LevelEvolutionSkeletonTest(unittest.TestCase):
    @staticmethod
    def _build_level(level_id: str) -> Level:
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
        setattr(level, "tasks", [])
        return level

    def test_level_evolution_skeleton_progression(self):
        with TemporaryDirectory() as temp_dir:
            runtime = QuestRuntime()
            runtime._inventory_store = InventoryStore(str(Path(temp_dir) / "inventory.db"))
            runtime._quest_state_store = QuestStateStore(str(Path(temp_dir) / "quest_state.db"))

            runtime.load_level_tasks(self._build_level("flagship_p4_skeleton"), "vivn")

            snapshot = runtime.get_debug_snapshot("vivn")
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot["level_state"]["current_stage"], "forest")
            self.assertEqual(snapshot["level_evolution"]["next_stage"], "camp")

            runtime.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "collect",
                    "payload": {"resource": "wood", "amount": 1},
                },
            )
            runtime.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "collect",
                    "payload": {"resource": "pork", "amount": 1},
                },
            )

            snapshot = runtime.get_debug_snapshot("vivn")
            self.assertEqual(snapshot["level_state"]["current_stage"], "camp")
            self.assertEqual(snapshot["level_evolution"]["next_stage"], "camp_npc")

            runtime.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "npc_talk",
                    "payload": {"npc_id": "npc_guard", "target": "npc_guard"},
                },
            )

            snapshot = runtime.get_debug_snapshot("vivn")
            self.assertEqual(snapshot["level_state"]["current_stage"], "camp_npc")
            self.assertEqual(snapshot["level_evolution"]["next_stage"], "camp_quest")

            runtime.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "npc_trigger",
                    "payload": {"npc_id": "npc_guard", "trigger": "npc_interact_guard"},
                },
            )

            snapshot = runtime.get_debug_snapshot("vivn")
            self.assertEqual(snapshot["level_state"]["current_stage"], "camp_quest")
            self.assertIsNone(snapshot["level_evolution"]["next_stage"])
            self.assertGreaterEqual(len(snapshot["level_state"].get("history", [])), 3)


if __name__ == "__main__":
    unittest.main()
