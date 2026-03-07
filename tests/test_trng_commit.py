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
from app.core.runtime.world_patch import build_world_patch_payload
from app.core.trng.transaction import TransactionShell


class TRNGCommitSkeletonTest(unittest.TestCase):
    def _arrange_shell_with_tx(self) -> tuple[TransactionShell, GraphState, InternalState, object]:
        shell = TransactionShell()
        committed_graph = GraphState()
        committed_state = InternalState(phase="intro", silence_count=0, tension=0)
        tx = shell.begin_tx(committed_graph, committed_state)
        shell.apply_event(tx, {"type": "input", "text": "commit me"})
        return shell, committed_graph, committed_state, tx

    def _state_hash(self, state: InternalState) -> str:
        payload = asdict(state)
        payload.pop("last_node_id", None)
        return stable_hash_v2(payload)

    def _graph_hash(self, graph: GraphState) -> str:
        return stable_hash_v2(asdict(graph))

    def _phase4_payload_hash(self, state: InternalState) -> str:
        runtime_state = {
            "phase": str(state.phase),
            "silence_count": int(state.silence_count),
            "tension": int(state.tension),
            "memory_flags": dict(state.memory_flags),
            "last_node_id": state.last_node_id,
            "talk_count": 0,
            "collected_resources": {},
            "npc_available": {},
            "triggers": {},
            "inventory": {"resources": []},
        }
        return stable_hash_v2(build_world_patch_payload(runtime_state))

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

        second_receipt = shell.commit(
            tx,
            committed_graph=committed_graph,
            committed_state=committed_state,
            rule_version="rule_v2_2",
        )
        self.assertEqual(receipt, second_receipt)
        self.assertEqual(tx.metadata.get("publish_count"), 1)
        self.assertEqual(tx.metadata.get("tx_status"), "committed")
        self.assertEqual(receipt["committed_state"].rule_version, receipt["rule_version"])

        commit_trace_count_before = sum(1 for row in tx.audit_trace if row.get("phase") == "commit")
        _ = shell.commit(
            tx,
            committed_graph=committed_graph,
            committed_state=committed_state,
            rule_version="rule_v2_2",
        )
        commit_trace_count_after = sum(1 for row in tx.audit_trace if row.get("phase") == "commit")
        self.assertEqual(commit_trace_count_before, 1)
        self.assertEqual(commit_trace_count_after, 1)

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
        self.assertEqual(receipt["base_state_hash"], tx.base_state_hash)
        self.assertEqual(receipt["committed_state_hash"], self._state_hash(receipt["committed_state"]))
        self.assertEqual(receipt["committed_graph_hash"], self._graph_hash(receipt["committed_graph"]))
        self.assertEqual(
            receipt["committed_state"].world_patch_hash,
            self._phase4_payload_hash(receipt["committed_state"]),
        )

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
        commit_trace = tx.audit_trace[-1]
        self.assertEqual(commit_trace.get("phase"), "commit")
        self.assertIsNone(commit_trace.get("event_id"))
        self.assertEqual(commit_trace.get("after_hash"), receipt.get("committed_state_hash"))

    def test_t4_transactional_replay_keeps_committed_hash_deterministic(self):
        # Arrange
        shell = TransactionShell()
        events = [
            {"type": "input", "text": "e1"},
            {"type": "input", "text": "e2"},
        ]

        committed_graph_1 = GraphState()
        committed_state_1 = InternalState(phase="intro", silence_count=0, tension=0)
        committed_graph_2 = GraphState()
        committed_state_2 = InternalState(phase="intro", silence_count=0, tension=0)

        tx1 = shell.begin_tx(committed_graph_1, committed_state_1)
        tx2 = shell.begin_tx(committed_graph_2, committed_state_2)

        for event in events:
            shell.apply_event(tx1, event)
            shell.apply_event(tx2, event)

        # Act
        receipt1 = shell.commit(
            tx1,
            committed_graph=committed_graph_1,
            committed_state=committed_state_1,
            rule_version="rule_v2_2",
        )
        receipt2 = shell.commit(
            tx2,
            committed_graph=committed_graph_2,
            committed_state=committed_state_2,
            rule_version="rule_v2_2",
        )

        # Assert
        self.assertEqual(receipt1["committed_state_hash"], receipt2["committed_state_hash"])
        self.assertEqual(receipt1["committed_graph_hash"], receipt2["committed_graph_hash"])


if __name__ == "__main__":
    unittest.main()
