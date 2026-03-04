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


class TRNGCommitSkeletonTest(unittest.TestCase):
    def _arrange_shell_with_tx(self) -> tuple[TransactionShell, GraphState, InternalState, object]:
        shell = TransactionShell()
        committed_graph = GraphState()
        committed_state = InternalState(phase="intro", silence_count=0, tension=0)
        tx = shell.begin_tx(committed_graph, committed_state)
        shell.apply_event(tx, {"type": "input", "text": "commit me"})
        return shell, committed_graph, committed_state, tx

    def test_t2_commit_publishes_graph_state_atomically(self):
        # Arrange
        shell, committed_graph, committed_state, tx = self._arrange_shell_with_tx()
        committed_graph_before = deepcopy(committed_graph)
        committed_state_before = deepcopy(committed_state)

        # Act
        receipt = shell.commit(
            tx,
            committed_graph=committed_graph,
            committed_state=committed_state,
            rule_version="rule_v2_2",
        )

        # Assert
        self.assertEqual(committed_graph, committed_graph_before)
        self.assertEqual(committed_state, committed_state_before)
        self.assertIsInstance(
            receipt,
            dict,
            "Phase5 fail-first: commit 应返回原子发布收据（dict），而不是内部元组",
        )

    def test_t2_commit_receipt_contains_required_hashes(self):
        # Arrange
        shell, committed_graph, committed_state, tx = self._arrange_shell_with_tx()

        # Act
        receipt = shell.commit(
            tx,
            committed_graph=committed_graph,
            committed_state=committed_state,
            rule_version="rule_v2_2",
        )

        # Assert
        self.assertIsInstance(receipt, dict, "Phase5 fail-first: commit receipt shape not implemented")
        self.assertIn("tx_id", receipt)
        self.assertIn("committed_state_hash", receipt)
        self.assertIn("committed_graph_hash", receipt)
        self.assertIn("commit_timestamp", receipt)

    def test_t6_commit_does_not_break_gate_contract(self):
        # Arrange
        shell, committed_graph, committed_state, tx = self._arrange_shell_with_tx()

        # Act
        receipt = shell.commit(
            tx,
            committed_graph=committed_graph,
            committed_state=committed_state,
            rule_version="rule_v2_2",
        )

        # Assert
        self.assertIsInstance(receipt, dict, "Phase5 fail-first: gate-compat receipt fields not implemented")
        self.assertIn("rule_version", receipt)
        self.assertIn("engine_version", receipt)
        self.assertIn("gate_compatibility", receipt)


if __name__ == "__main__":
    unittest.main()
