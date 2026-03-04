from __future__ import annotations

from typing import List

from .graph_state import GraphState, InternalState, StoryNode


class InvariantViolation(Exception):
    pass


def check_tx_invariants(
    *,
    committed_graph: GraphState,
    committed_state: InternalState,
    draft_graph: GraphState,
    draft_state: InternalState,
    tx_nodes: list[StoryNode],
    phase_change_count: int,
) -> List[str]:
    errors: List[str] = []

    if len(tx_nodes) < 1:
        errors.append("TX_MUST_CREATE_AT_LEAST_ONE_NODE")

    if not draft_graph.nodes:
        errors.append("GRAPH_EMPTY_AFTER_TX")

    if draft_graph.current_node_id != (draft_graph.nodes[-1].node_id if draft_graph.nodes else None):
        errors.append("CURRENT_NODE_NOT_AT_GRAPH_TAIL")

    if draft_state.last_node_id != draft_graph.current_node_id:
        errors.append("STATE_LAST_NODE_MISMATCH")

    if phase_change_count > 1:
        errors.append("PHASE_CHANGED_MORE_THAN_ONCE")

    if len(draft_graph.nodes) < len(committed_graph.nodes):
        errors.append("GRAPH_SHRINK_NOT_ALLOWED")

    if len(draft_graph.nodes) == len(committed_graph.nodes):
        errors.append("GRAPH_NOT_ADVANCED")

    if draft_state.silence_count < committed_state.silence_count:
        errors.append("SILENCE_COUNT_DECREASE_NOT_ALLOWED")

    return errors


def assert_tx_invariants(**kwargs) -> None:
    errors = check_tx_invariants(**kwargs)
    if errors:
        raise InvariantViolation(";".join(errors))
