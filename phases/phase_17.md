# Phase 17 – Flagship Arc Narrative Integration Pass

## Entry Conditions
- PHASE_16_COMPLETE = true in STATE.md.
- flagship_03, flagship_08, flagship_12, flagship_tutorial exist and validate.

## Scope
Integrate all flagship chapters into a continuous narrative arc:
- Ensure scene → beats → memory → branching → recommendations work without gaps.
- Add storyline_theme and emotional continuity fields across flagship levels.
- Normalize cinematic references and beat naming across all flagship levels.

## Allowed Changes
- backend/data/flagship_levels/*.json  
- backend/app/core/story/story_graph.py (weight adjustments only)  
- docs/STORY_STRUCTURE.md  
- docs/STATE.md  

## Tasks
1. Update each flagship level JSON:
   - Add `storyline_theme` field.
   - Ensure beats include `next_major_level` or branch hints.
   - Normalize cinematic ids (`flagship_03_intro`, `flagship_08_confront`, etc.).
2. Add emotional continuity cues in world_patch fields:
   - Subtle transitions between scenes (lighting/weather/tone).
3. Adjust StoryGraph:
   - Add small scoring bias for narrative continuity based on `storyline_theme`.
4. Update STORY_STRUCTURE.md:
   - Document flagship arc (Tutorial → 03 → 08 → 12 → Finale placeholder).

## Output Expectations
- Running Tutorial → flagship_03 → flagship_08 → flagship_12 feels like one arc.
- StoryGraph recommendations follow the flagship arc unless player choices strongly diverge.
- Cinematics do not conflict and load correctly across transitions.

## Risk Summary
- JSON schema drift could break level loading.
- Misaligned cinematic ids could fail at runtime.
- StoryGraph weighting must not override branching logic.

## Next-Phase Expectation
Phase 18 introduces player-generated levels (generative authoring) aligned with flagship narrative patterns.