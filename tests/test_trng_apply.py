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


class TRNGApplySkeletonTest(unittest.TestCase):
    def _arrange_committed(self) -> tuple[GraphState, InternalState]:
        return GraphState(), InternalState(phase="intro", silence_count=0, tension=0)

    def _state_hash(self, state: InternalState) -> str:
        payload = asdict(state)
        payload.pop("last_node_id", None)
        return stable_hash_v2(payload)

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
        self.assertEqual(tx.metadata.get("tx_status"), "active")
        self.assertIsNotNone(
            getattr(tx, "draft_state_hash", None),
            "Phase5 fail-first: apply_event 需输出 draft_state_hash",
        )
        self.assertIsNotNone(
            getattr(tx, "world_patch_payload_hash", None),
            "Phase5 fail-first: apply_event 需输出 world_patch_payload_hash",
        )
        self.assertEqual(tx.draft_state_hash, self._state_hash(tx.draft_state))
        self.assertEqual(tx.world_patch_payload_hash, self._phase4_payload_hash(tx.draft_state))

        apply_trace = tx.audit_trace[-1]
        self.assertEqual(apply_trace.get("tx_id"), tx.tx_id)
        self.assertEqual(apply_trace.get("phase"), "apply")
        self.assertTrue(bool(apply_trace.get("event_id")))
        self.assertEqual(apply_trace.get("after_hash"), tx.draft_state_hash)
        self.assertIsNone(apply_trace.get("failure_code"))
        self.assertGreaterEqual(len(tx.draft_patches), 1)
        self.assertEqual(tx.draft_patches[-1].get("event", {}).get("text"), "hello")

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
        self.assertEqual(
            getattr(tx1, "world_patch_payload_hash", None),
            getattr(tx2, "world_patch_payload_hash", None),
            "same base + same event sequence 应得到相同 world_patch_payload_hash",
        )
        self.assertEqual(len(tx1.draft_patches), len(events))
        self.assertEqual(len(tx2.draft_patches), len(events))

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
        reject_trace = tx.audit_trace[-1]
        self.assertEqual(reject_trace.get("phase"), "apply")
        self.assertEqual(reject_trace.get("failure_code"), "dry_run_failed")

    def test_t2_apply_after_commit_is_rejected_by_state_machine(self):
        # Arrange
        shell = TransactionShell()
        committed_graph, committed_state = self._arrange_committed()
        tx = shell.begin_tx(committed_graph, committed_state)
        shell.apply_event(tx, {"type": "input", "text": "before commit"})
        shell.commit(
            tx,
            committed_graph=committed_graph,
            committed_state=committed_state,
            rule_version="rule_v2_2",
        )

        # Act / Assert
        with self.assertRaises(RuntimeError):
            shell.apply_event(tx, {"type": "input", "text": "after commit"})


if __name__ == "__main__":
    unittest.main()
