# Shared World State Authority (STATE.md)

## 1. Current Phase
- Phase 1 · Unified Level Format
- Justification:
	- `backend/app/core/story/story_loader.py` enforces a consistent `Level` schema backed by the heart level JSON set under `backend/data/heart_levels/`.
	- `backend/app/core/story/story_graph.py` provides linear mainline traversal, validating that structured level IDs drive progression.
	- `system/mc_plugin/src/main/java/com/driftmc/DriftPlugin.java` and `backend/app/api/world_api.py` already rely on this shared format to load and render story content.

## 2. Current Goal
- Establish beat-driven narrative orchestration to unlock Phase 2 (StoryEngine with beat-based progression).

## 3. Progress – Done
- Capabilities already achieved:
	- Unified heart-level JSON with metadata, mood, and `world_patch` assets consumed by `story_loader`.
	- Automated stage setup via `StoryEngine.load_level_for_player`, including safe teleports and heuristic scene generation (`SceneGenerator`).
	- FastAPI + Minecraft plugin integration that can load levels, apply world patches, and expose REST/command entry points.

## 4. Progress – In Progress
- Capabilities missing:
	- No beat schema or runtime in the level data; `story_engine.advance` never references beat structures or `event_manager`.
	- Quest/task runtime (`backend/app/core/quest/runtime.py`) expects `level.tasks`, but the current `Level` dataclass lacks this field.
	- Tests (`backend/test_beats_v1.py`, `backend/test_quest_runtime.py`) target beat/task flows that the live engine does not currently satisfy.

## 5. Latest Code Updates (to be auto-updated from git diff or manual input)
```
No updates captured yet
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
- [ ] Extend the heart-level JSON schema and `Level` dataclass to encode beat sequences and task descriptors.
- [ ] Refactor `story_engine` to drive progression through explicit beats, wiring in `event_manager`, `scene_orchestrator`, and `quest_runtime` data flows.
- [ ] Update backend tests (`test_beats_v1.py`, `test_quest_runtime.py`) plus add new regression coverage for beat advancement and world patch synchronization.
- [ ] Confirm the Minecraft plugin applies beat-driven patches without regressions (world sync, minimap, command overrides).

## 8. Risks
- Quest runtime and beat tests reference structures that are absent from live level data, creating drift between planned and implemented behavior.
- Event and scene orchestration modules exist but remain unused, increasing the chance of regressions when integrating beats later.

## 9. Notes (high-level intent)
- This document is the central source of truth for shared world state; update collaboratively as plans evolve
