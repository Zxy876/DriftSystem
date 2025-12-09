# Shared World State Authority (STATE.md)

## 1. Current Phase
CURRENT_PHASE = 6
PHASE_1_COMPLETE = true
PHASE_1_5_COMPLETE = true
PHASE_2_COMPLETE = true
PHASE_3_COMPLETE = true
PHASE_4_COMPLETE = true
PHASE_5_COMPLETE = true

## 2. Current Goal
- Prepare launch checklist and polish pass now that the mainline exit system is live.

## 3. Progress – Done
- Capabilities already achieved:
	- Structured level extensions plus automated stage setup (scene generator, safe teleports, minimap integration).
	- Beat progression engine: StoryEngine registers level beats with `EventManager`, reacts to chat/near/interact triggers, and emits beat-scoped world patches.
	- QuestRuntime synchronizes beat-issued tasks, tracks rule references, and exposes `/world/story/rule-event` for bridge catalysts.
	- FastAPI endpoints and legacy plugin commands still load levels and apply world patches end-to-end.
	- Scene-aware plugin executor stores applied patches via `SceneLoader`/`SceneCleanupService`, auto-reversing builds when backend sends `_scene_cleanup`.
	- `RuleEventBridge` now forwards near-NPC events back to `/world/story/rule-event`, closing the basic rule trigger loop.
	- Scene metadata is now emitted via world patches, enabling plugin-side SceneAwareWorldPatchExecutor to track and clean scene sessions.
	- QuestRuntime TaskSessions normalize task definitions, track milestones/rewards, and respond to rule-event callbacks with aggregated nodes/world patches.
	- NPCBehaviorEngine records rulegraph bindings and emits dialogue/command/world patch updates when rule events fire.
	- `/world/story/rule-event` exposes task/NPC deltas directly for the plugin transport to consume.
	- Plugin bridge now applies rule-event `world_patch` payloads, emits quest/milestone chat beats, and dispatches backend `commands` to the server console.
	- Phase 4 contract is documented in `docs/PHASE4_TASK_CONTRACT.md`, covering task sessions, NPC bindings, and plugin duties.
	- ExitIntentDetector listens to Phase 5 exit aliases, calls `/world/story/end`, and applies the returned cleanup + hub teleport.
	- StoryEngine now records enter/exit trajectories, exposes exit profiles in `get_public_state`, and returns hub teleport summaries.

## 4. Progress – In Progress
- Capabilities under active review:
	- Verify KunmingLakeHub spawn safety for new hub snapshot.
	- Draft release notes highlighting exit summary UX tweaks.

## 5. Latest Code Updates (to be auto-updated from git diff or manual input)
```
- QuestRuntime now deduplicates task completion/milestone notifications when aggregating rule-trigger responses, preventing duplicate chat spam.
- StoryEngine, SceneAwareWorldPatchExecutor, and RuleEventBridge retain Phase 4 integration for rule-driven quest feedback.
```

## 6. File Map (summaries of project folder structures)
- `/backend`: Python backend stack with application package (`app/`), data assets (`data/`), startup scripts, and tests
- `/common`: Shared Python modules and protocol assets
- `/docs`: Documentation assets (STATE.md, README variants)
- `/mc_placeholder`: Placeholder Minecraft-related module and notes
- `/server`: Minecraft server configuration, logs, plugins, and world data
- `/system/mc_plugin`: Maven-based Minecraft plugin project (`pom.xml`, build scripts)
- `/tools`: Utility scripts (e.g., `validate_levels.py`)
- Root-level shell scripts (e.g., `build_and_deploy.sh`, `test_all.sh`) for building, testing, and deployment workflows

## 7. Next Actions (task-based, GPT readable)
- [ ] Run end-to-end story exit playtest (backend + plugin).
- [ ] Document exit summary UX in `docs/TUTORIAL_SYSTEM.md`.

## 8. Risks
- Hub teleport assumes KunmingLakeHub world is loaded; server ops should validate availability after restarts.
- Exit aliases are aggressive; future tuning may add per-level cooldowns to avoid accidental triggers.

## 9. Notes (high-level intent)
- This document is the central source of truth for shared world state; update collaboratively as plans evolve
