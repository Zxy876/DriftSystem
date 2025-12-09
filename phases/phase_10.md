# Phase 10 – StoryGraph & Replayability

## Entry Conditions
- PHASE_9_COMPLETE = true in docs/STATE.md.

## Scope
- Use the existing StoryGraph and trajectory logging to refine:
  - next-level recommendations
  - replay paths
  - simple branching based on completed tasks/levels.

## Allowed Changes
- backend/app/core/story/story_graph.py
- backend/app/core/story/story_engine.py (calls into StoryGraph)
- docs/STATE.md
- docs/PROJECT_VISION.md (update phases section if needed)

## Tasks
1. Add/update StoryGraph APIs so it can:
   - use trajectory history (enter/exit events) and task completions
     to decide the next recommended level.
2. Wire StoryEngine so:
   - `get_next_level` (or equivalent) respects StoryGraph recommendations.
3. Update STATE.md:
   - Set `PHASE_10_COMPLETE = true`.
   - Describe StoryGraph-driven recommendation behavior.

## Output Expectations
- After finishing or exiting a level, the system can recommend a
  “next chapter” that reflects the player’s path, instead of simple
  linear ordering.