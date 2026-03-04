from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.trng.graph_state import GraphState, InternalState
from app.core.trng.invariant_check import InvariantViolation
from app.core.trng.transaction import TransactionShell


class TRNGTransactionShellTest(unittest.TestCase):
    def setUp(self):
        self.shell = TransactionShell()
        self.committed_graph = GraphState()
        self.committed_state = InternalState()

    def test_draft_not_visible_before_commit(self):
        tx = self.shell.begin_tx(self.committed_graph, self.committed_state)
        self.shell.apply_event(tx, {"type": "input", "text": "hello"})

        self.assertEqual(len(self.committed_graph.nodes), 0)
        self.assertIsNone(self.committed_graph.current_node_id)
        self.assertIsNone(self.committed_state.last_node_id)
        self.assertGreaterEqual(len(tx.nodes), 1)

    def test_commit_makes_changes_visible_and_records_versions(self):
        tx = self.shell.begin_tx(self.committed_graph, self.committed_state)
        self.shell.apply_event(tx, {"type": "input", "text": "hello"})

        new_graph, new_state = self.shell.commit(
            tx,
            committed_graph=self.committed_graph,
            committed_state=self.committed_state,
            rule_version="rule_v2_2",
        )

        self.assertTrue(tx.committed)
        self.assertGreaterEqual(len(new_graph.nodes), 1)
        self.assertEqual(new_state.last_node_id, new_graph.current_node_id)
        self.assertEqual(new_state.rule_version, "rule_v2_2")
        self.assertIsInstance(new_state.world_patch_hash, str)
        self.assertTrue(bool(new_state.world_patch_hash))

    def test_commit_requires_at_least_one_node(self):
        tx = self.shell.begin_tx(self.committed_graph, self.committed_state)

        with self.assertRaises(InvariantViolation):
            self.shell.commit(
                tx,
                committed_graph=self.committed_graph,
                committed_state=self.committed_state,
                rule_version="rule_v2_2",
            )

    def test_rollback_keeps_committed_unchanged(self):
        tx = self.shell.begin_tx(self.committed_graph, self.committed_state)
        self.shell.apply_event(tx, {"type": "input", "text": "hello"})
        self.shell.rollback(tx)

        self.assertTrue(tx.rolled_back)
        self.assertEqual(len(self.committed_graph.nodes), 0)
        self.assertIsNone(self.committed_state.last_node_id)

    def test_invariant_failure_does_not_pollute_committed_state(self):
        tx = self.shell.begin_tx(self.committed_graph, self.committed_state)
        self.shell.apply_event(tx, {"type": "input", "text": "hello"})
        tx.phase_change_count = 2

        with self.assertRaises(InvariantViolation):
            self.shell.commit(
                tx,
                committed_graph=self.committed_graph,
                committed_state=self.committed_state,
                rule_version="rule_v2_2",
            )

        self.assertEqual(len(self.committed_graph.nodes), 0)
        self.assertIsNone(self.committed_state.last_node_id)
        self.assertIsNone(self.committed_state.rule_version)
        self.assertIsNone(self.committed_state.world_patch_hash)

    def test_dry_run_failure_creates_reject_node(self):
        shell = TransactionShell(dry_run_fn=lambda event, state: {"status": "FAIL", "reason": "dry_run_failed"})
        tx = shell.begin_tx(self.committed_graph, self.committed_state)
        shell.apply_event(tx, {"type": "input", "text": "hello"})

        self.assertGreaterEqual(len(tx.nodes), 2)
        self.assertEqual(tx.nodes[-1].node_type, "reject")
        self.assertEqual(tx.nodes[-1].event_type, "world_reject")


if __name__ == "__main__":
    unittest.main()
