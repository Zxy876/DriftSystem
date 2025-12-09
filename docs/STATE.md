# Shared World State Authority (STATE.md)

## 1. Current Phase
 CURRENT_PHASE = 20
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
PHASE_17_COMPLETE = true
PHASE_18_COMPLETE = true
PHASE_19_COMPLETE = true

## 2. Current Goal
- Ship the flagship campaign loop (tutorial → 03 → 08 → 12 → finale) and verify memory-driven endings.

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
	- Flagship arc chapters now share continuity metadata (`storyline_theme`, `next_major_level`, lighting/weather cues) and StoryGraph applies a theme-weighted bias to keep players on the flagship spine.

## 4. Progress – In Progress
- Capabilities under active review:
	- QA `flagship_final` cinematics and ensure camera control remains stable across both endings.
	- Observe 玩家对“踏入心悦主线”指令的使用率，调整提示时机。
	- Define analytics hooks for `xinyue.campaign_complete` ahead of Phase 21 instrumentation.

## 5. Latest Code Updates (to be auto-updated from git diff or manual input)
```
- Emotional weather system maps `xinyue.face_once` / `xinyue.escape_once` into level-defined patches and merges weather, lighting, and music in real time.
- SceneAwareWorldPatchExecutor now consumes `npc_emotion` payloads so hub NPC nameplates and dialogue tone react to emotional profiles.
- `GET /world/story/{player_id}/emotional-weather` returns the active profile, tone, and last applied patch for debugging.
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
- Flagship tutorial/03/08/12 JSONs now surface `storyline_theme`, `continuity`, and `next_major_level` metadata with lighting/weather transitions for smoother arc hand-offs.
- StoryGraph now applies a storyline theme continuity bias to keep flagship chapters linked unless player intent diverges.
- Emotional weather pipeline merges level-defined profiles, shifts weather/lighting/music on memory changes, and exposes hub tone updates via `/world/story/{player}/emotional-weather`.
- `/world/story/generate-level` synthesizes flagship-format user chapters, saves them under `generated/`, and hot-reloads StoryGraph + MiniMap layouts.
- Recommendation weights now track player-authored tag interest and highlight the latest generated chapter for seamless follow-up.
- First flagship campaign loop assembled: tutorial guidance updated, `flagship_final` delivers memory-dependent endings, continuity `next_major_level` links flagship chapters, and StoryGraph bias surfaces 终章推荐 entry points。
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
- [ ] Face-path 主线试玩：Tutorial → 03 → 08 → 12 → finale，核对记忆旗标与终章晨光演出。
- [ ] Escape-path 主线试玩：确保夜行循环结局触发正确的情绪补丁与标题。
- [ ] 监测 `/recommend` 输出，确认 StoryGraph 在完成 `flagship_12` 后优先推荐 `flagship_final`。
- [ ] 收集玩家对“踏入心悦主线”提示的反馈，必要时加入自动提示节奏。
- [ ] 草拟 Phase 20 发布说明，记录终章分支与教程更新。
- [ ] 规划 `xinyue.campaign_complete` 分析维度，并与 Phase 21 指标对齐。
- [ ] 回收 QA 数据，评估是否需要为主线新增分支回放指令或日志。

## 8. Risks
- Hub teleport assumes KunmingLakeHub world is loaded; server ops should validate availability after restarts.
- Exit aliases are aggressive; future tuning may add per-level cooldowns to avoid accidental triggers.

## 9. Notes (high-level intent)
- This document is the central source of truth for shared world state; update collaboratively as plans evolve
