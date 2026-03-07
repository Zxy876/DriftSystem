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
from app.core.quest.runtime import QuestRuntime


class InventoryPersistenceTest(unittest.TestCase):
    def test_inventory_store_persists_across_instances(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "inventory.db"

            first_store = InventoryStore(str(db_path))
            first_store.add_resource("vivn", "wood", 2)
            first_store.add_resource("vivn", "torch", 1)

            second_store = InventoryStore(str(db_path))
            self.assertEqual(second_store.get_resources("vivn"), {"wood": 2, "torch": 1})

    def test_quest_runtime_persists_collect_without_active_state(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "inventory.db"
            store = InventoryStore(str(db_path))

            runtime = QuestRuntime()
            runtime._inventory_store = store

            response = runtime.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "collect",
                    "payload": {
                        "item_type": "wood",
                        "resource": "wood",
                        "amount": 1,
                        "quest_event": "collect_wood",
                    },
                },
            )

            self.assertIsNone(response)
            self.assertEqual(runtime.get_inventory_resources("vivn"), {"wood": 1})

    def test_quest_runtime_inventory_survives_runtime_recreation(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "inventory.db"

            first_runtime = QuestRuntime()
            first_runtime._inventory_store = InventoryStore(str(db_path))
            first_runtime.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "collect",
                    "payload": {
                        "item_type": "pork",
                        "resource": "pork",
                        "amount": 2,
                        "quest_event": "collect_pork",
                    },
                },
            )

            second_runtime = QuestRuntime()
            second_runtime._inventory_store = InventoryStore(str(db_path))
            self.assertEqual(second_runtime.get_inventory_resources("vivn"), {"pork": 2})

    def test_inventory_store_canonicalizes_collect_aliases(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "inventory.db"

            store = InventoryStore(str(db_path))
            store.add_resource("vivn", "oak_log", 2)
            store.add_resource("vivn", "spruce_log", 1)
            store.add_resource("vivn", "raw_porkchop", 1)
            store.add_resource("vivn", "cooked_porkchop", 2)

            self.assertEqual(store.get_resources("vivn"), {"wood": 3, "pork": 3})

    def test_runtime_merges_legacy_alias_rows_on_read(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "inventory.db"
            store = InventoryStore(str(db_path))

            with store._connect() as conn:
                store._ensure_schema(conn)
                conn.execute(
                    "INSERT INTO player_inventory (player_id, resource, amount, updated_at_ms) VALUES (?, ?, ?, ?)",
                    ("vivn", "oak_log", 2, 1),
                )
                conn.execute(
                    "INSERT INTO player_inventory (player_id, resource, amount, updated_at_ms) VALUES (?, ?, ?, ?)",
                    ("vivn", "wood", 1, 1),
                )
                conn.execute(
                    "INSERT INTO player_inventory (player_id, resource, amount, updated_at_ms) VALUES (?, ?, ?, ?)",
                    ("vivn", "raw_porkchop", 1, 1),
                )
                conn.execute(
                    "INSERT INTO player_inventory (player_id, resource, amount, updated_at_ms) VALUES (?, ?, ?, ?)",
                    ("vivn", "cooked_porkchop", 2, 1),
                )

            runtime = QuestRuntime()
            runtime._inventory_store = store

            self.assertEqual(runtime.get_inventory_resources("vivn"), {"wood": 3, "pork": 3})

    def test_quest_runtime_collect_item_aliases_persist_as_canonical(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "inventory.db"

            runtime = QuestRuntime()
            runtime._inventory_store = InventoryStore(str(db_path))

            runtime.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "collect",
                    "payload": {
                        "item_type": "birch_log",
                        "amount": 2,
                        "quest_event": "collect_birch_log",
                    },
                },
            )
            runtime.handle_rule_trigger(
                "vivn",
                {
                    "event_type": "collect",
                    "payload": {
                        "item_type": "cooked_porkchop",
                        "amount": 1,
                        "quest_event": "collect_pork",
                    },
                },
            )

            self.assertEqual(runtime.get_inventory_resources("vivn"), {"wood": 2, "pork": 1})


if __name__ == "__main__":
    unittest.main()
