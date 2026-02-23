# DRIFT_MEMORY_SCENE_READINESS

> **Audit Date:** 2026-02-23  
> **Scope:** Validate whether Drift can today support: reproduce a specific memory scene in Minecraft → trigger build → record the process → output continuously usable material for video capture.

---

## EXECUTABLE TODAY

These capabilities are fully implemented and require no additional code.

### 1. Resource text query → deterministic resource_id selection
- `ResourceCatalog` + `ResourceSnapshot.find_candidates()` + `CreationTransformer` are operational.
- Text token → scored candidates → top-1 match returned as `resource_id`.  No LLM involved.
- 32 resources indexed; aliases and Chinese labels both work (`"祭坛"` → `drift:altar_frame`).
- **Evidence:** `backend/app/core/creation/transformer.py` · `backend/app/core/creation/resource_snapshot.py`

### 2. Execution timeline logging (PatchTransactionLog)
- Every dispatched template is written to `data/patch_logs/transactions.log` as JSONL.
- Each entry records: `patch_id`, `template_id`, `step_id`, `commands[]`, `status`, `created_at` (ISO-8601 UTC), `metadata`.
- Log is append-only and survives process restarts.
- **Evidence:** `backend/app/core/world/patch_transaction.py`

### 3. Command safety validation without LLM
- `validate_patch_template()` + `analyze_commands()` classify every command before dispatch.
- Enforces `execution_tier` (`safe_auto` / `needs_confirm` / `blocked`) without any live inference.
- Unsafe commands (`op`, `stop`, shell injection) are rejected at validation time.
- **Evidence:** `backend/app/core/world/command_safety.py` · `backend/app/core/creation/validation.py`

### 4. Multi-step command dispatch within a single CreationPlan
- `PlanExecutor.auto_execute()` iterates all `safe_auto` templates in order and calls `RconClient.run()` for each.
- Each step's status (`validated`, `pending`, `failed`) is recorded to the transaction log.
- **Evidence:** `backend/app/core/world/plan_executor.py`

### 5. RCON client — zero external dependencies
- `RconClient` implements the RCON wire protocol using only stdlib `socket` + `struct`.
- `RconClient.verify()` provides a lightweight credential check before dispatching any commands.
- **Evidence:** `backend/app/core/minecraft/rcon_client.py`

### 6. WorldBuildEventLog — structured build timeline (new)
- Added `backend/app/core/world/world_listener.py`.
- Records every dispatched MC command as a typed JSONL event: `scene_id`, `plan_id`, `step_id`, `event_type`, `command`, `timestamp`, `metadata` (coordinates parsed from `setblock`/`fill`).
- Classifies commands: `block_place` · `block_fill` · `function_call` · `entity_spawn` · `structure_place`.
- **Evidence:** `backend/app/core/world/world_listener.py`

### 7. `run_plan.py` — CLI entry point (new)
- Added `scripts/run_plan.py`.
- Loads a `CreationPlan` JSON, runs `PatchExecutor.dry_run()` then `PlanExecutor.auto_execute()` against RCON.
- Supports `--dry-run` (validate only), `--scene-id` (recorded in event log).
- No server, no LLM, no HTTP: `python scripts/run_plan.py plan.json --dry-run`.
- **Evidence:** `scripts/run_plan.py` · `backend/data/scenes/example_plan.json`

---

## REQUIRES MINOR GLUE

These capabilities are partially present; the gap is a small script or data edit.

### 1. Build commands for `drift:*` resources
- **Gap:** All 6 `drift:` catalog entries (`drift:altar_frame`, `drift:exhibit_frame`, `drift:garden_bundle`, `drift:machine_core`, `drift:portal_ring`, `drift:statue_base`) have `"commands": []`.
- Without commands, `PatchExecutor` produces `no_commands` skips for every `drift:` template.
- **Fix:** Add concrete `setblock` / `fill` sequences to `backend/data/transformer/resource_catalog.seed.json` for each `drift:` resource.  No code change required — just data.

### 2. Placeholder substitution for `gm4:*` resources
- Several resources carry commands like `execute in {world} positioned {x} {y} {z} run ...`.
- `detect_placeholders()` flags them; templates with unresolved placeholders get `execution_tier=needs_confirm` and are skipped.
- **Fix:** A `~10`-line substitution pass before calling `PatchExecutor.dry_run()` — replace `{world}` / `{x}` / `{y}` / `{z}` with scene coordinates from the scene definition.

### 3. Scene-level grouping in PatchTransactionLog
- The transaction log records individual templates but has no `scene_id` field.
- `WorldBuildEventLog.record_commands()` already accepts `scene_id`; `run_plan.py --scene-id` already propagates it.
- **Remaining gap:** `PatchTransactionLog.record()` metadata does not include `scene_id`.  A one-line addition to the metadata dict in `run_plan.py` suffices.

### 4. Multi-plan scene sequence runner
- `run_plan.py` executes one plan per invocation.
- A scene definition (`example_scene.json`) has a `plan_sequence` array, but no runner iterates it.
- **Fix:** Add a `--scene` flag to `run_plan.py` that reads `plan_sequence` from the scene JSON and invokes `auto_execute()` for each plan in order.  ~30 lines.

---

## HARD BLOCKERS

These missing capabilities prevent the complete 5-step recording workflow today.

### BLOCKER 1: `drift:*` resources have no build commands
- All 6 custom Drift structures (`altar_frame`, `exhibit_frame`, etc.) are registered in the catalog but have `"commands": []`.
- **Impact:** Any scene using Drift-specific assets cannot be instantiated.  The pipeline passes validation but produces zero world changes.
- **Required:** Concrete `setblock` / `fill` / `place structure` sequences for each `drift:` resource.

### BLOCKER 2: Resource resolution is score-based, not uniquely locked
- `find_candidates()` returns up to 3 candidates above a 0.35 threshold.
- `CreationTransformer` selects `candidates[0]` (highest score), but when two resources share equal scores the selection is insertion-order dependent, not deterministic.
- **Impact:** Scene reproduction is not bit-for-bit reproducible across catalog rebuilds.
- **Required:** Deterministic tie-breaking (e.g., lexicographic `resource_id` sort) or an explicit `resource_id` field in the scene definition that bypasses fuzzy matching.

### BLOCKER 3: No MC-side block event listener
- `WorldBuildEventLog` (added) records what Drift *dispatches* to the server.
- There is no Java/Spigot `BlockPlaceEvent` / `BlockBreakEvent` listener wired to structured output.
- **Impact:** If a build command is accepted by RCON but fails silently in MC (out-of-bounds, bad block ID, permissions), the timeline shows success while the world was not changed.  Video narrator cannot trust the log matches visible world state.
- **Required:** A lightweight Spigot/Paper plugin listener that emits structured events (JSON over stdout or a file) when blocks are actually placed or broken, annotated with `plan_id` from a scoreboard or player tag.

### BLOCKER 4: No Scene container abstraction in the codebase
- `example_scene.json` (added) defines the schema, but no Python class or loader exists.
- `SceneGenerator` exists but generates environment patches from level text — it does not interpret a `scene_id` / `location` / `plan_sequence` structure.
- **Impact:** Cannot load a scene definition and automatically bind resources to coordinates without manual JSON editing per scene.
- **Required:** A `SceneDefinition` dataclass + `SceneLoader` that parses `scene_id`, `location`, `assets_used`, and `plan_sequence` into executable `CreationPlan` objects.

### BLOCKER 5: No inter-step pacing / recording-friendly execution
- `PlanExecutor.auto_execute()` sends all commands as fast as RCON accepts them.
- For OBS-recorded builds, blocks must be placed at a pace visible to the camera (typically 1–5 blocks per second, or step-by-step with a delay).
- **Impact:** A 20-command plan completes in under a second; video captures nothing meaningful.
- **Required:** A configurable `step_delay_ms` parameter (or a paced runner) that introduces a pause between template steps, allowing OBS to capture the progressive build.

---

## NOT REQUIRED FOR THIS PROJECT

Do not build or extend these systems for the memory scene recording workflow.

| System | Why excluded |
|--------|--------------|
| `StoryEngine` / beat system | Drives narrative dialogue; irrelevant to build recording |
| `CreationIntentClassifier` / LLM inference | Scene is specified explicitly; no chat input needed |
| NPC behavior system | No NPCs appear in build recording workflow |
| `EventManager` (keyword / proximity triggers) | Story interaction events; not build events |
| Emotional weather / ambient layer | Visual ambiance, not build pipeline |
| `WorldEngine.tick()` physics | Player physics; build pipeline is server-side only |
| Minimap / HUD rendering | UI overlay; not part of build→record loop |
| New DSL grammar or schema changes | Existing `CreationPlan` JSON format is sufficient |
| Architecture refactoring | Existing module boundaries are adequate for the audit scope |

---

## 5-STEP RECORDING WORKFLOW — STATUS

| Step | Description | Status |
|------|-------------|--------|
| 1 | Specify a memory scene (`scene_id`, `location`, `assets_used`) | ⚠️ Schema exists (`example_scene.json`); no Python loader yet |
| 2 | Select already-catalogued resources | ✅ `ResourceCatalog` + `find_candidates()` operational |
| 3 | Trigger build via `run_plan.py` | ✅ CLI entry point added; RCON pipeline functional |
| 4 | Drift records the full process | ⚠️ Drift-side timeline complete (`WorldBuildEventLog`); MC-side block confirmation missing |
| 5 | OBS records without post-logic | ❌ Commands fire instantly; no pacing for camera-visible build |

**Conclusion:** Steps 2 and 3 are unblocked today. Steps 1, 4, and 5 are partially unblocked but each have a hard blocker that must be resolved before a clean recording session is achievable.
