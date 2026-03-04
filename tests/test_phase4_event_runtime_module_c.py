from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.runtime.interaction_event import create_interaction_event
from app.core.runtime.interaction_event_log import InteractionEventLog
from app.core.runtime.state_reducer import replay_event_log_to_patch, runtime_state_hash


class Phase4EventRuntimeModuleCTest(unittest.TestCase):
    def _build_event_log(self) -> InteractionEventLog:
        log = InteractionEventLog()
        log.append(
            create_interaction_event(
                event_type="talk",
                event_id="evt_001",
                player_id="p1",
                npc_id="npc_mother",
                timestamp_ms=1000,
                data={"relationship_delta": 0.4, "threshold": 0.6},
                anchor={"base_x": 10, "base_y": 64, "base_z": 2, "anchor_mode": "fixed"},
            )
        )
        log.append(
            create_interaction_event(
                event_type="talk",
                event_id="evt_002",
                player_id="p1",
                npc_id="npc_mother",
                timestamp_ms=1100,
                data={"relationship_delta": 0.3, "threshold": 0.6},
                anchor={"base_x": 10, "base_y": 64, "base_z": 2, "anchor_mode": "fixed"},
            )
        )
        log.append(
            create_interaction_event(
                event_type="collect",
                event_id="evt_003",
                player_id="p1",
                timestamp_ms=1200,
                data={"resource": "paper_crane", "amount": 2},
                anchor={"base_x": 10, "base_y": 64, "base_z": 2, "anchor_mode": "fixed"},
            )
        )
        log.append(
            create_interaction_event(
                event_type="trigger",
                event_id="evt_004",
                player_id="p1",
                timestamp_ms=1300,
                data={"trigger": "memory.mother"},
                anchor={"base_x": 10, "base_y": 64, "base_z": 2, "anchor_mode": "fixed"},
            )
        )
        return log

    def test_interaction_event_model_validates_type(self):
        with self.assertRaises(ValueError):
            create_interaction_event(
                event_type="move",
                event_id="evt_bad",
                player_id="p1",
                timestamp_ms=1,
            )

    def test_append_only_log_rejects_duplicate_and_mutation(self):
        log = InteractionEventLog()
        e = create_interaction_event(
            event_type="collect",
            event_id="evt_dup",
            player_id="p1",
            timestamp_ms=1,
            data={"resource": "wood", "amount": 1},
        )
        log.append(e)

        with self.assertRaises(ValueError):
            log.append(e)

        with self.assertRaises(RuntimeError):
            log.update("evt_dup", {"type": "trigger"})
        with self.assertRaises(RuntimeError):
            log.delete("evt_dup")
        with self.assertRaises(RuntimeError):
            log.clear()

    def test_reducer_is_deterministic_for_same_log(self):
        log_a = self._build_event_log()
        log_b = self._build_event_log()

        replay_a = replay_event_log_to_patch(log_a.list_events())
        replay_b = replay_event_log_to_patch(log_b.list_events())

        self.assertEqual(replay_a["state_hash"], replay_b["state_hash"])
        self.assertEqual(replay_a["payload_hash"], replay_b["payload_hash"])
        self.assertEqual(replay_a["world_patch"]["input_state_hash"], replay_a["state_hash"])

    def test_event_replay_test_same_log_same_state_and_payload_hash(self):
        events = self._build_event_log().list_events()

        first = replay_event_log_to_patch(events)
        second = replay_event_log_to_patch(events)

        self.assertEqual(first["state_hash"], second["state_hash"])
        self.assertEqual(first["payload_hash"], second["payload_hash"])
        self.assertEqual(first["runtime_state"], second["runtime_state"])
        self.assertEqual(first["world_patch"], second["world_patch"])
        self.assertEqual(first["world_patch"]["payload"], second["world_patch"]["payload"])
        self.assertEqual(first["world_patch"]["input_state_hash"], first["state_hash"])
        self.assertEqual(first["world_patch"]["payload_hash"], first["payload_hash"])

        state = first["runtime_state"]
        self.assertEqual(state["npc_available"].get("npc_mother"), True)
        self.assertEqual(runtime_state_hash(state), first["state_hash"])


if __name__ == "__main__":
    unittest.main()
