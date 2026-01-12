 StoryState Template Integration Plan

## Objectives
- Embed template answers inside narrative beats and NPC dialogue tasks so world interactions produce actionable data.
- Capture narrative milestones in `StoryState` and drive CityPhone coverage, capability, and readiness scores automatically.
- Close the loop from exploration to build execution while preserving a manual override path via template buttons.

## Trigger Entry: Narrative / NPC Interactions
1. **Author mapping**: For each story template entry, record the narrative task or NPC dialogue that should deliver the answer. Maintain this mapping in a YAML/JSON source checked into `mc_plugin/story_templates/`.
2. **Agent contract**: Update StoryStateAgent and supporting scripts so that, on task completion, they call `StoryStateManager.apply_template(template_id, patch)` or write directly to `StoryState` fields.
3. **Patch payload**: Standardize the `StoryStatePatch` structure. Required keys: `logic`, `resources`, `risks`, `notes`, `milestones`. Optional metadata: `source_task`, `npc_id`, `timestamp`.
4. **Runtime hook**: In the quest/mission pipeline, emit a `story_template_completed` event once the player selects an answer or finishes the mission branch. The handler invokes StoryStateAgent with the prepared patch.

## Milestones and CityPhone Synchronization
1. **Schema extension**: Extend `StoryState` with a `milestones` dict (`{template_id: {"status": "complete", "source": "npc"}}`) and a `last_updated` timestamp.
2. **Process logic**: Inside `StoryStateManager.process()`:
   - Merge incoming patches into the active `StoryState`.
   - Recompute `coverage`, `build_capability`, and `ready_for_build` when a milestone flips to `complete`.
   - Emit a `story_state_updated` signal for downstream consumers.
3. **CityPhone backend**: Ensure the API already serving StoryState returns the expanded schema. Add derived fields `templates_completed` and `coverage_delta` for quick UI refreshes.
4. **CityPhone UI**: Display per-template status, source badges (`NPC`, `Research`, `Manual`), and highlight new completions on the next refresh.

## Feedback Loop Wiring
1. **World interaction** triggers story or research tasks.
2. **Narrative/NPC agents** produce `StoryStatePatch` or write directly to StoryState.
3. **StoryStateManager** merges patches, recalculates scores, and updates readiness flags.
4. **CityPhone UI** fetches the latest StoryState and reflects coverage, score, and readiness changes.
5. **BuildPlanAgent** reads the updated StoryState, unlocks the next planning phase, and passes work to BuildExecutor, whose results alter the world state for the next loop.

## Implementation Checklist
- [ ] Finalize template-to-task mapping document and share with narrative design.
- [ ] Define `StoryStatePatch` contract in `common/protocols/story_state.py` and add unit tests.
- [ ] Extend `StoryState` data model with `milestones`, `source`, and timestamps; migrate existing saves.
- [ ] Update `StoryStateManager.apply_template` and `process` to merge new fields and trigger recomputation.
- [ ] Add backend event handler that listens for quest completion and invokes the manager with the correct patch.
- [ ] Expose new fields through the CityPhone API and document response changes.
- [ ] Update CityPhone UI to show status badges and score deltas; include "Provided by NPC" tooltip text.
- [ ] Keep the manual template fill button active as a fallback path and log manual interventions for analytics.

## Operational Notes
- Provide logging in StoryStateManager for every patch (source, template_id, delta) to aid debugging.
- Include analytics hooks to measure how often NPC interactions complete templates versus manual fills.
- Plan regression tests covering: patch merge, milestone-derived score increases, UI refresh displaying new status, and BuildPlanAgent progression.
- Document the authoring workflow so narrative designers understand how to register new milestones.
