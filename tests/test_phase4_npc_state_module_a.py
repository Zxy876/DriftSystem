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
from app.core.runtime.npc_state import (
    NPC_STATE_VERSION,
    apply_relationship_delta,
    create_npc_state,
    evaluate_npc_availability,
    npc_state_hash,
    normalize_npc_state,
)
from app.core.runtime.state_reducer import reduce_event_log


class Phase4NpcStateModuleATest(unittest.TestCase):
    def test_a1_npc_state_versioned_structure(self):
        state = create_npc_state(
            npc_id="npc_mother",
            relationship_value=0.55,
            threshold=0.6,
            anchor={"base_x": 10, "base_y": 65, "base_z": -2, "anchor_mode": "fixed"},
        )
        payload = normalize_npc_state(state)

        self.assertEqual(payload["version"], NPC_STATE_VERSION)
        self.assertEqual(payload["npc_id"], "npc_mother")
        self.assertEqual(payload["relationship_value"], 0.55)
        self.assertEqual(payload["threshold"], 0.6)
        self.assertEqual(payload["npc_available"], False)
        self.assertEqual(payload["anchor"]["base_x"], 10)

    def test_a2_threshold_to_npc_available(self):
        self.assertEqual(
            evaluate_npc_availability(relationship_value=0.6, threshold=0.6),
            True,
        )
        self.assertEqual(
            evaluate_npc_availability(relationship_value=0.59, threshold=0.6),
            False,
        )

        base = create_npc_state(
            npc_id="npc_guard",
            relationship_value=0.4,
            threshold=0.6,
        )
        upgraded = apply_relationship_delta(base, delta=0.25, threshold=0.6)
        self.assertEqual(upgraded["npc_available"], True)
        self.assertEqual(upgraded["relationship_value"], 0.65)

    def test_a3_npc_state_hash_is_deterministic(self):
        state_a = create_npc_state(
            npc_id="npc_mother",
            relationship_value=0.7,
            threshold=0.6,
            anchor={"base_x": 1, "base_y": 64, "base_z": 1, "anchor_mode": "fixed"},
        )
        state_b = create_npc_state(
            npc_id="npc_mother",
            relationship_value=0.7,
            threshold=0.6,
            anchor={"base_z": 1, "base_y": 64, "base_x": 1, "anchor_mode": "fixed"},
        )
        state_c = create_npc_state(
            npc_id="npc_mother",
            relationship_value=0.71,
            threshold=0.6,
            anchor={"base_x": 1, "base_y": 64, "base_z": 1, "anchor_mode": "fixed"},
        )

        hash_a = npc_state_hash(state_a)
        hash_b = npc_state_hash(state_b)
        hash_c = npc_state_hash(state_c)

        self.assertEqual(hash_a, hash_b)
        self.assertNotEqual(hash_a, hash_c)

    def test_reducer_contains_npc_state_map(self):
        events = [
            create_interaction_event(
                event_type="talk",
                event_id="evt_talk_1",
                player_id="p1",
                npc_id="npc_mother",
                timestamp_ms=1000,
                data={"relationship_delta": 0.4, "threshold": 0.6},
            ),
            create_interaction_event(
                event_type="talk",
                event_id="evt_talk_2",
                player_id="p1",
                npc_id="npc_mother",
                timestamp_ms=1100,
                data={"relationship_delta": 0.25, "threshold": 0.6},
            ),
        ]

        state = reduce_event_log(events)
        self.assertIn("npc_state", state)
        self.assertIn("npc_mother", state["npc_state"])

        mother = state["npc_state"]["npc_mother"]
        self.assertEqual(mother["version"], NPC_STATE_VERSION)
        self.assertEqual(mother["npc_available"], True)
        self.assertEqual(mother["relationship_value"], 0.65)
        self.assertEqual(state["npc_available"]["npc_mother"], True)


if __name__ == "__main__":
    unittest.main()
