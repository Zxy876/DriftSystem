from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.trng.graph_state import GraphState, InternalState
from app.core.trng.transaction import TransactionShell


class TRNGApplySkeletonTest(unittest.TestCase):
    def _arrange_committed(self) -> tuple[GraphState, InternalState]:
        return GraphState(), InternalState(phase="intro", silence_count=0, tension=0)

    def test_t1_apply_does_not_mutate_committed_state(self):
        # Arrange
        shell = TransactionShell()
        committed_graph, committed_state = self._arrange_committed()
        tx = shell.begin_tx(committed_graph, committed_state)
        committed_graph_before = deepcopy(committed_graph)
        committed_state_before = deepcopy(committed_state)

        # Act
        shell.apply_event(tx, {"type": "input", "text": "hello"})

        # Assert
        self.assertEqual(committed_graph, committed_graph_before)
        self.assertEqual(committed_state, committed_state_before)
        self.assertGreaterEqual(len(tx.nodes), 1)
        self.assertIsNotNone(
            getattr(tx, "draft_state_hash", None),
            "Phase5 fail-first: apply_event 需输出 draft_state_hash",
        )
        self.assertIsNotNone(
            getattr(tx, "world_patch_payload_hash", None),
            "Phase5 fail-first: apply_event 需输出 world_patch_payload_hash",
        )

    def test_t4_apply_same_event_sequence_is_deterministic(self):
        # Arrange
        shell = TransactionShell()
        committed_graph, committed_state = self._arrange_committed()
        tx1 = shell.begin_tx(committed_graph, committed_state)
        tx2 = shell.begin_tx(committed_graph, committed_state)
        events = [
            {"type": "input", "text": "e1"},
            {"type": "input", "text": "e2"},
        ]

        # Act
        for event in events:
            shell.apply_event(tx1, event)
            shell.apply_event(tx2, event)

        # Assert
        self.assertIsNotNone(
            getattr(tx1, "draft_state_hash", None),
            "Phase5 fail-first: deterministic replay 依赖 draft_state_hash",
        )
        self.assertEqual(
            getattr(tx1, "draft_state_hash", None),
            getattr(tx2, "draft_state_hash", None),
            "same base + same event sequence 应得到相同 draft_state_hash",
        )

    def test_t5_apply_failure_creates_reject_audit_trace(self):
        # Arrange
        shell = TransactionShell(dry_run_fn=lambda _event, _state: {"status": "FAIL", "reason": "dry_run_failed"})
        committed_graph, committed_state = self._arrange_committed()
        tx = shell.begin_tx(committed_graph, committed_state)

        # Act
        shell.apply_event(tx, {"type": "input", "text": "trigger reject"})

        # Assert
        self.assertTrue(any(node.node_type == "reject" for node in tx.nodes))
        self.assertIsNotNone(
            getattr(tx, "audit_trace", None),
            "Phase5 fail-first: apply reject 路径需保留 audit_trace",
        )


if __name__ == "__main__":
    unittest.main()
