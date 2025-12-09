# Phase 14 – Cinematic Engine & Scene Transitions

## Entry Conditions
- PHASE_13_COMPLETE = true in docs/STATE.md.

## Scope
Add cinematic presentation for major beats:
- camera movements
- fade-in/out
- slow-motion
- synchronized particles + sound + environment
- chapter intro sequences

## Allowed Changes
- system/mc_plugin/src/main/java/.../cinematic/*
- backend/app/core/story/story_engine.py (per-beat cinematic metadata)
- docs/CINEMATIC_SYSTEM.md
- docs/STATE.md

## Tasks
1. Add Cinematic Engine:
   - `CinematicController.java`
   - Features:
     - screen fade (black fade-in/out)
     - camera angle set/offset target
     - play-sequence(list<actions>) runner
     - slow-motion multiplier

2. Add support for beat-bound cinematics:
   - narrative.beats[n].scene_patch → plugin translates to cinematic action sequence
   - example:
     ```
     fade_out(1.2)
     teleport
     fade_in(1.0)
     camera_pan_to("mountain_summit")
     play_sound("ambient.summit")
     particles("snow_blast")
     ```

3. Add `/cinematic test` for testing sequences.

4. Update STATE.md
   - PHASE_14_COMPLETE = true

## Output Expectations
- Entering level_03 triggers mountain cinematic
- level_01_finish triggers racing finale cinematic