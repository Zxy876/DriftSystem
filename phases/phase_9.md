# Phase 9 – Cinematic & Moment Design

## Entry Conditions
- PHASE_8_COMPLETE = true in docs/STATE.md.

## Scope
- Enhance a small set of signature moments with:
  - stronger title/subtitle usage
  - sound/music
  - particles and environment transitions
  - beat-triggered changes

## Allowed Changes
- backend/data/heart_levels/*.json
- backend/app/core/story/story_engine.py (beat-to-patch helpers)
- docs/STATE.md

## Tasks
1. Pick 2–3 chapters (e.g. opening chapter, father argument, summit scene).
2. For each:
   - Attach a specific beat (e.g. conflict/climax) to:
     - a title/subtitle
     - sound/music change
     - environment transition (time/weather)
3. Ensure changes are emitted via existing world_patch mechanisms.
4. Update STATE.md:
   - Set `PHASE_9_COMPLETE = true`.
   - Record that cinematic beats are in place for key chapters.

## Output Expectations
- Players can feel a noticeable “moment” when hitting major beats in those
  chapters (without introducing new engine concepts).