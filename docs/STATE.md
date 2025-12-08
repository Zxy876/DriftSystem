# Shared World State Authority (STATE.md)

## 1. Current Phase
- Phase 1.5 · Narrative Scaffold
- Justification:
	- `backend/app/core/story/level_schema.py` introduces the beats/scene/rules/tasks/exit dataclasses and `ensure_level_extensions`, which `story_engine.load_level_for_player` now invokes to extend legacy levels.
	- `backend/app/core/story/story_engine.py` records scene handles, beat pointers, and rule listener registration stubs, proving the Phase 1.5 hooks are present (even if mostly placeholders).
	- `backend/app/core/quest/runtime.py` and `backend/app/api/world_api.py` expose the new rule-trigger/stroy-enter endpoints required for future beat/rule orchestration, while `system/mc_plugin` remains unchanged pending the bridge implementation.

## 2. Current Goal
- Establish beat-driven narrative orchestration to unlock Phase 2 (StoryEngine with beat-based progression).

## 3. Progress – Done
- Capabilities already achieved:
	- Unified heart-level JSON with metadata, mood, and `world_patch` assets consumed by `story_loader`.
	- Automated stage setup via `StoryEngine.load_level_for_player`, including safe teleports and heuristic scene generation (`SceneGenerator`).
	- FastAPI + Minecraft plugin integration that can load levels, apply world patches, and expose REST/command entry points.
	- Phase 1.5 scaffolding in place: `backend/app/core/story/level_schema.py` for structured extensions, StoryEngine hooks for scenes/beats/rules, QuestRuntime rule listener storage, and `/world/story/*` endpoints for enter/end/rule-event workflows.

## 4. Progress – In Progress
- Capabilities missing:
	- `backend/data/heart_levels/*.json` files still contain only `world_patch` data; no beats/tasks/rules are hydrated into the new schema during load.
	- `story_engine.advance` continues to ignore beats and `event_manager`; beat pointers recorded in Phase 1.5 hooks do not affect runtime behavior.
	- QuestRuntime rule triggers (`handle_rule_trigger`) and `/world/story/rule-event` remain unused by the Minecraft plugin, leaving rule-driven tasks unverified.
	- Scene/Exit lifecycle bridging is absent on the plugin side; cleanup and teleport handoff rely on legacy safe teleport logic.
	- Regression tests for beats/tasks (`backend/test_beats_v1.py`, `backend/test_quest_runtime.py`) are stale relative to the new schema expectations.

## 5. Latest Code Updates (to be auto-updated from git diff or manual input)
```
- Phase 1.5 backend skeleton committed (level schema, StoryEngine hooks, QuestRuntime scaffolding, `/world/story/*` endpoints).
- Vision and schema design docs added (`docs/PROJECT_VISION.md`, `docs/LEVEL_FORMAT.md`).
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
- [ ] Hydrate beats/scene/rules/tasks/exit data into `backend/data/heart_levels/*.json` and extend `story_loader` to populate `LevelExtensions` from disk.
- [ ] Evolve `story_engine.advance` to consume beat definitions, emit world patches, and coordinate with `event_manager`.
- [ ] Wire QuestRuntime rule triggers through `/world/story/rule-event` and deliver actionable updates back to the player.
- [ ] Implement SceneLoader / SceneCleanupService / RuleEventBridge in `system/mc_plugin` to apply and clean Phase 1.5 scenes.
- [ ] Refresh backend regression tests (`backend/test_beats_v1.py`, `backend/test_quest_runtime.py`) for the new schema and beat/task flows.

## 8. Risks
- Quest runtime and beat tests reference structures that are absent from live level data, creating drift between planned and implemented behavior.
- Phase 1.5 HTTP endpoints and rule-listener hooks are unexercised, so regressions may surface when the Minecraft bridge is introduced.

## 9. Notes (high-level intent)
- This document is the central source of truth for shared world state; update collaboratively as plans evolve
