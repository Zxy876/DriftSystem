from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.trng.graph_state import GraphState, InternalState
from app.core.executor.canonical_v2 import stable_hash_v2
from app.core.trng.transaction import TransactionShell


class TRNGBeginSkeletonTest(unittest.TestCase):
    def _arrange_committed(self) -> tuple[GraphState, InternalState]:
        return GraphState(), InternalState(phase="intro", silence_count=0, tension=0)

    def _state_hash(self, state: InternalState) -> str:
        payload = asdict(state)
        payload.pop("last_node_id", None)
        return stable_hash_v2(payload)

    def test_t1_begin_draft_isolation(self):
        # Arrange
        shell = TransactionShell()
        committed_graph, committed_state = self._arrange_committed()
        committed_graph_before = deepcopy(committed_graph)
        committed_state_before = deepcopy(committed_state)

        # Act
        tx = shell.begin_tx(committed_graph, committed_state)

        # Assert
        self.assertTrue(bool(getattr(tx, "tx_id", "")))
        self.assertEqual(committed_graph, committed_graph_before)
        self.assertEqual(committed_state, committed_state_before)
        self.assertIsNotNone(
            getattr(tx, "base_state_hash", None),
            "Phase5 fail-first: begin_tx 应提供 base_state_hash 绑定 committed baseline",
        )
        self.assertEqual(tx.base_state_hash, self._state_hash(committed_state))

        begin_trace = tx.audit_trace[0]
        self.assertEqual(begin_trace.get("tx_id"), tx.tx_id)
        self.assertEqual(begin_trace.get("phase"), "begin")
        self.assertEqual(begin_trace.get("before_hash"), tx.base_state_hash)
        self.assertEqual(begin_trace.get("after_hash"), tx.base_state_hash)
        self.assertIsNone(begin_trace.get("event_id"))
        self.assertIsNone(begin_trace.get("failure_code"))

    def test_t4_begin_replay_entry_is_deterministic(self):
        # Arrange
        shell = TransactionShell()
        committed_graph, committed_state = self._arrange_committed()

        # Act
        tx1 = shell.begin_tx(committed_graph, committed_state)
        tx2 = shell.begin_tx(committed_graph, committed_state)

        # Assert
        self.assertNotEqual(getattr(tx1, "tx_id", None), getattr(tx2, "tx_id", None))
        self.assertIsNotNone(
            getattr(tx1, "base_state_hash", None),
            "Phase5 fail-first: tx_context 需暴露 replay 入口哈希",
        )
        self.assertEqual(
            getattr(tx1, "base_state_hash", None),
            getattr(tx2, "base_state_hash", None),
            "same committed base 应映射到相同 base_state_hash",
        )


if __name__ == "__main__":
    unittest.main()
