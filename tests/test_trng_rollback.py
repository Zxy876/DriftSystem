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


class TRNGRollbackSkeletonTest(unittest.TestCase):
    def _arrange_committed(self) -> tuple[GraphState, InternalState]:
        return GraphState(), InternalState(phase="intro", silence_count=0, tension=0)

    def test_t3_rollback_keeps_committed_unchanged(self):
        # Arrange
        shell = TransactionShell()
        committed_graph, committed_state = self._arrange_committed()
        tx = shell.begin_tx(committed_graph, committed_state)
        shell.apply_event(tx, {"type": "input", "text": "to be rolled back"})
        committed_graph_before = deepcopy(committed_graph)
        committed_state_before = deepcopy(committed_state)

        # Act
        receipt = shell.rollback(tx)

        # Assert
        self.assertEqual(committed_graph, committed_graph_before)
        self.assertEqual(committed_state, committed_state_before)
        self.assertIsInstance(
            receipt,
            dict,
            "Phase5 fail-first: rollback 应返回收据（dict）以支持审计",
        )

    def test_t3_rollback_is_idempotent(self):
        # Arrange
        shell = TransactionShell()
        committed_graph, committed_state = self._arrange_committed()
        tx = shell.begin_tx(committed_graph, committed_state)
        shell.apply_event(tx, {"type": "input", "text": "to be rolled back twice"})

        # Act
        first_receipt = shell.rollback(tx)
        second_receipt = shell.rollback(tx)

        # Assert
        self.assertIsInstance(first_receipt, dict, "Phase5 fail-first: first rollback receipt not implemented")
        self.assertIsInstance(second_receipt, dict, "Phase5 fail-first: second rollback receipt not implemented")
        self.assertEqual(first_receipt, second_receipt, "rollback 需要幂等可观察结果")

    def test_t5_rollback_after_apply_failure_is_safe(self):
        # Arrange
        shell = TransactionShell(dry_run_fn=lambda _event, _state: {"status": "FAIL", "reason": "dry_run_failed"})
        committed_graph, committed_state = self._arrange_committed()
        tx = shell.begin_tx(committed_graph, committed_state)
        shell.apply_event(tx, {"type": "input", "text": "should reject"})
        committed_graph_before = deepcopy(committed_graph)
        committed_state_before = deepcopy(committed_state)

        # Act
        receipt = shell.rollback(tx)

        # Assert
        self.assertTrue(any(node.node_type == "reject" for node in tx.nodes))
        self.assertEqual(committed_graph, committed_graph_before)
        self.assertEqual(committed_state, committed_state_before)
        self.assertIsInstance(receipt, dict, "Phase5 fail-first: rollback reject-path receipt not implemented")


if __name__ == "__main__":
    unittest.main()
