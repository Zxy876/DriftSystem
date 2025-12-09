# Phase 7 – NPC Visuals & Behavior Polish

## Entry Conditions
- PHASE_6_COMPLETE = true in docs/STATE.md.

## Scope
- Make NPCs in key Heart levels visually and behaviorally distinct, using:
  - npc_behavior_engine hooks
  - level JSON `npc_skins` / NPC behavior definitions
  - existing quest/runtime + rule-event bridge

## Allowed Changes
- backend/data/heart_levels/*.json
- backend/app/core/npc/npc_behavior_engine.py
- docs/STATE.md
- docs/PHASE4_TASK_CONTRACT.md (append NPC notes if needed)

## Tasks
1. Identify 3–5 key chapters (e.g. level_1, level_3, tutor/newbie level).
2. For their main NPCs:
   - Add behavior definitions (patrol / climb / interact / quest) consistent
     with current runtime support.
   - Attach skin references (names only, no new asset pipeline).
3. Ensure rule listeners and QuestRuntime integration remain valid.
4. Update STATE.md:
   - Set `PHASE_7_COMPLETE = true`.
   - Note NPC polish as a completed milestone.

## Output Expectations
- In-game, players can clearly distinguish NPC roles by:
  - name, behavior patterns, and dialogue.