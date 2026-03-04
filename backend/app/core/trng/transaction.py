from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import json
import time
from uuid import uuid4
from typing import Any, Callable, Dict, Optional

from .graph_state import GraphState, InternalState, StoryNode
from .invariant_check import assert_tx_invariants


DryRunFn = Callable[[Dict[str, Any], InternalState], Dict[str, Any]]


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _state_hash(state: InternalState) -> str:
    payload = asdict(state)
    payload.pop("last_node_id", None)
    return _stable_hash(payload)


def _graph_hash(graph: GraphState) -> str:
    return _stable_hash(asdict(graph))


class CommitReceipt(dict):
    def __iter__(self):
        return iter((self.get("committed_graph"), self.get("committed_state")))


@dataclass
class Transaction:
    tx_id: str
    base_state_hash: str
    root_from_node: Optional[str]
    draft_graph: GraphState
    draft_state: InternalState | None
    draft_patch: Dict[str, Any] | None = None
    draft_state_hash: str | None = None
    world_patch_payload_hash: str | None = None
    audit_trace: list[Dict[str, Any]] = field(default_factory=list)
    nodes: list[StoryNode] = field(default_factory=list)
    phase_change_count: int = 0
    committed: bool = False
    rolled_back: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class TransactionShell:
    def __init__(self, *, dry_run_fn: DryRunFn | None = None) -> None:
        self._dry_run_fn = dry_run_fn

    def begin_tx(self, committed_graph: GraphState, committed_state: InternalState) -> Transaction:
        base_state_hash = _state_hash(committed_state)
        return Transaction(
            tx_id=f"tx_{uuid4().hex[:12]}",
            base_state_hash=base_state_hash,
            root_from_node=committed_graph.current_node_id,
            draft_graph=deepcopy(committed_graph),
            draft_state=deepcopy(committed_state),
            draft_state_hash=base_state_hash,
        )

    def apply_event(self, tx: Transaction, event: Dict[str, Any]) -> None:
        if tx.draft_state is None:
            raise RuntimeError("TX_DRAFT_STATE_NOT_AVAILABLE")

        event_type = str(event.get("type", "input")).strip().lower() or "input"
        event_text = str(event.get("text", "")).strip()

        if event_type == "timeout":
            node = StoryNode(
                node_id=f"node_{uuid4().hex[:10]}",
                node_type="silence",
                text=event_text or "silence",
                event_type=event_type,
                state_patch={"silence_count": tx.draft_state.silence_count + 1},
            )
        else:
            node = StoryNode(
                node_id=f"node_{uuid4().hex[:10]}",
                node_type="normal",
                text=event_text or "event",
                event_type=event_type,
                state_patch={},
            )

        self._append_node(tx, node)

        dry_run = self._run_world_dry_run(event, tx.draft_state)
        tx.metadata["world_dry_run"] = dry_run
        tx.draft_patch = {
            "event": deepcopy(event),
            "dry_run": deepcopy(dry_run),
        }

        if dry_run.get("status") != "PASS":
            reject_node = StoryNode(
                node_id=f"node_{uuid4().hex[:10]}",
                node_type="reject",
                text=str(dry_run.get("reason", "world_dry_run_failed")),
                event_type="world_reject",
                state_patch={},
            )
            self._append_node(tx, reject_node)

        tx.draft_state_hash = _state_hash(tx.draft_state)
        tx.world_patch_payload_hash = _stable_hash(
            {
                "world_patch_hash": dry_run.get("world_patch_hash"),
                "event_type": event_type,
                "last_node_id": tx.draft_state.last_node_id,
            }
        )
        tx.audit_trace.append(
            {
                "tx_id": tx.tx_id,
                "stage": "apply",
                "event_type": event_type,
                "draft_state_hash": tx.draft_state_hash,
                "world_patch_payload_hash": tx.world_patch_payload_hash,
                "status": str(dry_run.get("status", "UNKNOWN")),
                "reason": dry_run.get("reason"),
            }
        )
        tx.metadata["audit_trace"] = tx.audit_trace

    def commit(
        self,
        tx: Transaction,
        *,
        committed_graph: GraphState,
        committed_state: InternalState,
        rule_version: str,
    ) -> CommitReceipt:
        if tx.draft_state is None:
            raise RuntimeError("NOTHING_TO_COMMIT")

        assert_tx_invariants(
            committed_graph=committed_graph,
            committed_state=committed_state,
            draft_graph=tx.draft_graph,
            draft_state=tx.draft_state,
            tx_nodes=tx.nodes,
            phase_change_count=tx.phase_change_count,
        )

        tx.draft_state.rule_version = rule_version
        dry_run_meta = tx.metadata.get("world_dry_run")
        if isinstance(dry_run_meta, dict):
            tx.draft_state.world_patch_hash = str(dry_run_meta.get("world_patch_hash") or "") or None

        tx.draft_state_hash = _state_hash(tx.draft_state)
        committed_graph_hash = _graph_hash(tx.draft_graph)

        receipt = CommitReceipt(
            {
                "tx_id": tx.tx_id,
                "base_state_hash": tx.base_state_hash,
                "committed_state_hash": tx.draft_state_hash,
                "committed_graph_hash": committed_graph_hash,
                "commit_timestamp": time.time(),
                "rule_version": rule_version,
                "engine_version": str(tx.metadata.get("engine_version") or "engine_v2_1"),
                "gate_compatibility": {"gate5": True, "gate6": True, "gate7": True},
                "committed_graph": tx.draft_graph,
                "committed_state": tx.draft_state,
            }
        )

        tx.committed = True
        tx.audit_trace.append(
            {
                "tx_id": tx.tx_id,
                "stage": "commit",
                "committed_state_hash": receipt["committed_state_hash"],
                "committed_graph_hash": receipt["committed_graph_hash"],
            }
        )
        tx.metadata["audit_trace"] = tx.audit_trace
        tx.metadata["commit_receipt"] = receipt
        return receipt

    def rollback(self, tx: Transaction) -> Dict[str, Any]:
        prior = tx.metadata.get("rollback_receipt")
        if isinstance(prior, dict):
            return prior

        tx.rolled_back = True
        tx.draft_state = None
        tx.draft_patch = None

        receipt: Dict[str, Any] = {
            "tx_id": tx.tx_id,
            "rollback_reason": str(tx.metadata.get("rollback_reason") or "user"),
            "base_state_hash": tx.base_state_hash,
        }
        tx.audit_trace.append(
            {
                "tx_id": tx.tx_id,
                "stage": "rollback",
                "rollback_reason": receipt["rollback_reason"],
                "base_state_hash": tx.base_state_hash,
            }
        )
        tx.metadata["audit_trace"] = tx.audit_trace
        tx.metadata["rollback_receipt"] = receipt
        return receipt

    def _append_node(self, tx: Transaction, node: StoryNode) -> None:
        if tx.draft_state is None:
            raise RuntimeError("TX_DRAFT_STATE_NOT_AVAILABLE")

        tx.nodes.append(node)
        tx.draft_graph.append_node(node)
        tx.draft_state.last_node_id = node.node_id

        patch = node.state_patch or {}
        if "silence_count" in patch:
            tx.draft_state.silence_count = int(patch["silence_count"])
        if "phase" in patch and patch["phase"] != tx.draft_state.phase:
            tx.draft_state.phase = str(patch["phase"])
            tx.phase_change_count += 1
        if "tension" in patch:
            tx.draft_state.tension = int(patch["tension"])

    def _run_world_dry_run(self, event: Dict[str, Any], state: InternalState) -> Dict[str, Any]:
        if self._dry_run_fn is None:
            return {
                "status": "PASS",
                "world_patch_hash": f"dry_{state.phase}_{state.silence_count}",
            }
        payload = self._dry_run_fn(event, state)
        if not isinstance(payload, dict):
            return {"status": "FAIL", "reason": "INVALID_DRY_RUN_PAYLOAD"}
        status = str(payload.get("status", "FAIL")).upper()
        if status not in {"PASS", "FAIL"}:
            return {"status": "FAIL", "reason": "INVALID_DRY_RUN_STATUS"}
        return payload
