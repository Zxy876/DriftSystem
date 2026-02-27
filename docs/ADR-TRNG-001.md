# ADR-TRNG-001: StoryEngine lacks transactional semantics for multi-instance deployment

Status: Proposed

Date: 2026-02-27

Authors: Audit by repo inspection

---

## Context

A read-only audit of the repository shows the runtime `StoryEngine` is instantiated as a module-level singleton and maintains the runtime story state primarily in process memory. Key implementation artifacts inspected include:

- [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py)
- [backend/app/api/world_api.py](backend/app/api/world_api.py)
- [backend/app/core/ai/deepseek_agent.py](backend/app/core/ai/deepseek_agent.py)
- [backend/app/core/story/story_graph.py](backend/app/core/story/story_graph.py)
- [backend/app/core/ideal_city/story_state_repository.py](backend/app/core/ideal_city/story_state_repository.py)

The audit focused on structural consistency and multi-instance suitability (no code changes performed).

## Problem / Findings

1. Runtime state topology
- `StoryEngine` holds per-player runtime state in `self.players` (a process-local dict). The module exposes a single instantiated object (`story_engine = StoryEngine()`), and `world_api` calls this instance directly.
- Other modules also hold in-process caches and singletons (LLM cache and dispatcher in `deepseek_agent`, `StoryGraph` in `story_engine`, `world_engine` in `world_api`).

2. Lack of transactional boundaries
- `advance(...)` performs multiple in-place updates to player state (`nodes`, `messages`, `pending_patches`, `beat_state`, `ended`, etc.) during a single call. There is no draft/commit separation nor a global rollback mechanism.
- Several side effects happen in the same call: AI decision, appending nodes/messages, updating graph/trajectory/minimap, applying quest updates, composing emotional patches, and persisting exhibit instances (when enabled). These are not performed atomically.

3. Partial-update and exception risk
- Sequential writes to multiple in-memory targets (player dict, `StoryGraph.trajectory`, `MiniMap`, quest runtime) create opportunities for partial updates if an exception occurs mid-flow.

4. Persistence and replay
- A local `StoryStateRepository` exists (file-based JSON snapshot) but is not integrated as a primary, unified event-log for `StoryEngine` updates. No append-only event log or transaction log suitable for replay across instances was found.

5. Concurrency and multi-instance assumptions
- The design assumes process-local state (no shared store). Concurrent requests or multiple process instances will observe divergent state; there is no coordination layer for multi-instance serialization.

## Evidence (representative pointers)
- `story_engine` is instantiated at module end: [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py)
- `world_api` directly calls `story_engine.advance(...)` per request: [backend/app/api/world_api.py](backend/app/api/world_api.py)
- `advance(...)` mutates `self.players[player_id]` at multiple points and merges patches inline: [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py)
- `deepseek_agent` exposes process-global cache / dispatcher threads: [backend/app/core/ai/deepseek_agent.py](backend/app/core/ai/deepseek_agent.py)
- `StoryStateRepository` is file-based JSON snapshot with a local Lock, but appears used by a separate ideal_city flow and not as a unified transactional log for `story_engine`: [backend/app/core/ideal_city/story_state_repository.py](backend/app/core/ideal_city/story_state_repository.py)

## Impact

- Multi-instance deployment (e.g., Gunicorn workers, Kubernetes replicas, Railway instances) without sticky sessions or an external coordination layer will produce divergent and inconsistent per-player story state.
- Partial updates inside `advance(...)` can leave state inconsistent after failures, undermining reproducibility and making safe retries unsafe (non-idempotent).
- Lack of an append-only event stream or transaction log prevents deterministic replay-based recovery across instances.

## Risk Level

High — the current `StoryEngine` design relies on process-local mutable state and lacks transactional semantics required for safe cloud multi-instance deployment.

## Decision

Record the audit finding: *`StoryEngine` as implemented is not safe to run as multiple uncoordinated cloud instances (no sticky sessions / no shared state) without introducing an external coordination or redesign that provides transactional boundaries and shared persistence.*

(Decision is an audit record only; no implementation actions are performed in this ADR.)

## Notes / Caveats

- This ADR is based on repository inspection and the files cited above. If the runtime deployment environment includes an external, centralized state/coordination layer or a proxy that serializes `advance` calls and consolidates state, the practical risk may be reduced—but no such integration was discovered in the inspected code paths.

---

End of ADR-TRNG-001
