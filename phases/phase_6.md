# Phase 6 – Heart Levels v2 Content Pass

## Entry Conditions
- PHASE_5_COMPLETE = true in docs/STATE.md.

## Scope
- Upgrade existing heart level JSON files under `backend/data/heart_levels/`
  to the v2.0 schema (narrative + scene + rules + tasks + exit) described in:
  - docs/LEVEL_FORMAT.md
  - docs/LEVEL_JSON_CAPABILITY_REPORT.md

## Allowed Changes
- backend/data/heart_levels/*.json
- docs/LEVEL_FORMAT.md (minor clarifications only)
- docs/STATE.md (progress and flags)

## Tasks
1. For each `level_*.json`:
   - Ensure presence of: `narrative.beats`, `scene`, `rules`, `tasks`, `exit`
     where appropriate for that chapter.
   - Preserve existing `world_patch` behavior but, when possible, express
     scene metadata using the `_scene` pattern.
2. Keep changes **backward compatible**:
   - Never remove legacy fields that StoryEngine currently relies on.
3. Update STATE.md:
   - Set `PHASE_6_COMPLETE = true`.
   - Add a short summary under "Progress – Done" about Heart Level v2 rollout.

## Output Expectations
- Modified JSON files validate under the existing loader.
- No Python or Java code changes in this phase.