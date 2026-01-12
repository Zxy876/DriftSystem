# Build Failure Feedback Loop Plan

## Purpose
Enable players to recover from failed build executions through conversational guidance. When a build plan cannot complete, the narrative agent should surface the cause, propose fixes, and orchestrate the required world/NPC steps so the player can succeed on the next attempt.

## End-to-End Flow
1. **Build execution fails**
   - BuildExecutor reports status (e.g., `missing_materials`, `blocked_location`).
   - IdealCityPipeline captures the failure payload and related metadata (plan id, commands, missing mods, logs).
2. **StoryState update**
   - Pipeline writes failure context to `StoryState` (new fields such as `last_plan_status`, `build_feedback`, `pending_reasons`).
   - Failed plan milestones flip to `pending` to signal unfinished work.
3. **Narrative agent intervention**
   - StoryStateAgent reads failure context on the next player interaction.
   - If the player asks for help (“建不成怎么办”), agent returns a `StoryStatePatch` containing:
     - Suggested remediation milestones (e.g., `collect_night_materials`).
     - Follow-up guidance text and optional NPC pointers.
4. **World & NPC response**
   - World API applies the patch, triggering CityPhone to display actionable tasks.
   - Optional: spawn helper NPC/dialogue or update quest board to point the player to missing requirements.
5. **Player retries**
   - Player completes new milestones (resource gathering, blueprint validation, etc.).
   - CityPhone reflects readiness gain. When requirements met, `/drift build` triggers a new plan.
6. **Feedback closure**
   - Successful execution clears failure flags, logs analytics event (`build_recovery_success`).
   - Narrative agent acknowledges success and documents the resolution.

## Required Changes
### 1. StoryState Enhancements
- Add fields:
  - `last_plan_status`: literal (`"completed"`, `"failed"`, `"pending"`).
  - `build_feedback`: structured record of last failure (cause, missing items, timestamp).
  - `pending_reasons`: human-readable todos surfaced to UI.
- Ensure serialization/migration handles existing saves.

### 2. Pipeline Hooks
- In `IdealCityPipeline._load_executed_plan`, detect non-success states and populate a `BuildFailureContext` object.
- Extend `apply_story_patch` or create `record_build_feedback(player_id, scenario_id, context)` to merge failure info into StoryState.
- Emit analytics/log events for failure cases.

### 3. Narrative Agent Logic
- Update `StoryStateAgentContext` to include `build_feedback`.
- Implement `StoryStateAgent.infer()` branch:
  - If `build_feedback` present and player intent indicates help-seeking, return patch with remediation milestones and guidance text.
  - Optionally adjust motivation/logic scores to reflect partial progress.

### 4. CityPhone UI Updates
- Display build failure summary in plan panel (e.g., "缺少：夜市布景材料").
- Highlight agent-suggested remedial tasks under `pending_reasons` with source badges (`agent`, `npc`).
- Add notification banner when agent provides a recovery plan.

### 5. World Integration
- In `world_api.story_rule_event`, recognize remediation milestones and trigger NPC/world actions (e.g., spawn vendor, unlock chest).
- Allow agent to enqueue scripted scenes that help the player gather missing items or negotiate with NPCs.

### 6. Authoring & Templates
- Extend `story_templates.yaml` with failure-specific milestones (e.g., `resource_night_market_missing`).
- Provide default `expected_patch` for each failure type so the agent can quickly populate guidance.
- Document author workflow for tagging NPC dialogue as recovery hints.

## Rollout Checklist
- [ ] Schema: implement new StoryState fields and migrations.
- [ ] Pipeline: capture failure context and persist via `apply_story_patch`.
- [ ] Agent: support help-seeking intents and remediation patches.
- [ ] CityPhone: show failure banners and recovery tasks.
- [ ] World: hook remediation milestones to NPC/world events.
- [ ] Templates: author YAML entries for common failure scenarios.
- [ ] Tests: add coverage for failure -> agent guidance -> recovery success path.
- [ ] Docs: update tutorial & roadmap to include recovery loop guidance.

## Success Metrics
- Percentage of failed builds where the player receives actionable guidance within one interaction.
- Rate at which remediation milestones are completed after failure.
- Time from failure to next successful build execution.
- Player feedback (qualitative) indicating clarity of guidance and perceived agency.
