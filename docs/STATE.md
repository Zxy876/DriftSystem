# Shared World State Authority (STATE.md)

## 1. Current Phase
CURRENT_PHASE = 17
PHASE_1_COMPLETE = true
PHASE_1_5_COMPLETE = true
PHASE_2_COMPLETE = true
PHASE_3_COMPLETE = true
PHASE_4_COMPLETE = true
PHASE_5_COMPLETE = true
PHASE_6_COMPLETE = true
PHASE_7_COMPLETE = true
PHASE_8_COMPLETE = true
PHASE_9_COMPLETE = true
PHASE_10_COMPLETE = true
PHASE_11_COMPLETE = true
PHASE_12_COMPLETE = true
PHASE_13_COMPLETE = true
PHASE_14_COMPLETE = true
PHASE_15_COMPLETE = true
PHASE_16_COMPLETE = true

## 2. Current Goal
- Pilot the branching choice UI and collect story-path telemetry for upcoming narrative tweaks.

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
	- QuestRuntime now returns task titles/hints and RuleEventBridge renders progress/milestones with streamlined quest log chat formatting.
	- Cinematic beats now trigger for level_01’s checkpoint/finish, level_03’s summit climb, and the tutorial launch portal with coordinated titles, particles, and environment shifts.
	- NPCBehaviorEngine records rulegraph bindings and emits dialogue/command/world patch updates when rule events fire.
	- `/world/story/rule-event` exposes task/NPC deltas directly for the plugin transport to consume.
	- Plugin bridge now applies rule-event `world_patch` payloads, emits quest/milestone chat beats, and dispatches backend `commands` to the server console.
	- Phase 4 contract is documented in `docs/PHASE4_TASK_CONTRACT.md`, covering task sessions, NPC bindings, and plugin duties.
	- ExitIntentDetector listens to Phase 5 exit aliases, calls `/world/story/end`, and applies the returned cleanup + hub teleport.
	- StoryEngine now records enter/exit trajectories, exposes exit profiles in `get_public_state`, and returns hub teleport summaries.
	- Heart level content migrated to schema v2.0: every chapter carries beats/scene/rules/tasks/exit scaffolding and emits `_scene` metadata for the plugin cleanup loop.
	- Key NPC hubs (level_01, level_03, tutorial_level) now expose polished behaviors, rule listeners, and `npc_skins` metadata to make roles visually distinct.
	- StoryGraph now canonicalizes numeric level ids, records player trajectories, and produces weighted next-level recommendations consumed by StoryEngine.
	- Minecraft plugin surfaces StoryGraph recommendations via `/recommend` HUD with action-bar prompts and clickable chat shortcuts.
	- Quest log HUD renders active tasks/milestones via `/questlog`, auto-refreshing on level entry, rule events, and exits with milestone action-bar cues.
	- Story choices UI powers beat-defined branches: ChoicePanel renders options, RuleEventBridge forwards selections, and StoryGraph biases recommendations based on recorded decisions.

## 4. Progress – In Progress
- Capabilities under active review:
	- Verify KunmingLakeHub spawn safety for new hub snapshot.
	- Draft release notes highlighting exit summary UX tweaks.
	- Sample-play Heart Level v2 beats to collect tuning notes for upcoming phase work.
	- Capture qualitative feedback on refreshed NPC behaviors before rolling polish to later chapters.

## 5. Latest Code Updates (to be auto-updated from git diff or manual input)
```
- QuestRuntime now exposes `active_tasks` snapshots with remaining counts, task titles, and milestone names for HUD rendering.
- New `/world/story/{player_id}/quest-log` endpoint delivers quest log payloads and accompanying summary metadata.
- QuestLogHud surfaces structured quest details via `/questlog`, auto-refreshes on level entry, and fires action-bar notifications on milestones/completions.
	- NPC dialogue HUD renders cinematic conversations with typing cadence, right-click activation, and nameplate styling; skin metadata now flows from scenes into the plugin.
- RuleEventBridge forwards quest snapshots to the HUD and relays milestone events without duplicating chat spam.
- `level_01.json` exit metadata repaired so StoryGraph loads all heart levels without JSON warnings.
- CinematicController sequences fades, slow-motion, particles, and camera pans for heart-level beats and `/cinematic test` validation.
- StoryEngine `CINEMATIC_LIBRARY` now emits preset cinematics for level_01 podium and level_03 summit transitions.
- ChoicePanel intercepts `story_choice` nodes, renders numbered options, and emits `rule_event` payloads so StoryEngine can resolve branches.
- StoryEngine records `choice_history`, surfaces prompt metadata, and updates StoryGraph with `next_level`/tag affinities to personalize recommendations.
	- Flagship arc now persists `xinyue.*` memory flags (admitted pain, face/escape loops, summit progress) to retarget NPC tone, cinematics, and StoryGraph affinity.
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
- [ ] Conduct dev-server smoke test for polished NPC behaviors (level_01, level_03, tutorial_level).
- [ ] Aggregate player transcripts to decide which mid-game chapters receive the next cosmetic pass.
- [ ] Run branching playtest covering at least two beats to verify rule events, recommendations, and analytics output.
- [ ] Schedule multiplayer playtest to observe how players use the new recommendation & quest log HUD.
- [ ] Document quest log onboarding copy in `docs/TUTORIAL_SYSTEM.md`.
- [ ] Backfill `scene.npc_skins` metadata for remaining heart levels (26 entries outstanding).

## 8. Risks
- Hub teleport assumes KunmingLakeHub world is loaded; server ops should validate availability after restarts.
- Exit aliases are aggressive; future tuning may add per-level cooldowns to avoid accidental triggers.

## 9. Notes (high-level intent)
- This document is the central source of truth for shared world state; update collaboratively as plans evolve
