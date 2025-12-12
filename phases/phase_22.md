# Phase 22 – Unify Flagship Chapter Task Logic (03 / 08 / 12 / Final)

## Entry Conditions
- Phase 21 tutorial tasks working
- Chapters 03/08/12 load properly but tasks may not complete

## Goals
1. Migrate all flagship chapter tasks to the Phase 20 schema.
2. Ensure all milestone events map correctly to RuleEventBridge.
3. Make memory-driven branches (face / escape) update tasks properly.

## Required Changes
- backend/data/flagship_levels/flagship_03.json
- backend/data/flagship_levels/flagship_08.json
- backend/data/flagship_levels/flagship_12.json
- backend/data/flagship_levels/flagship_final.json
  + Add canonical `milestone_event` to each beat.
  + Add missing `rule_event` for all narrative branches.
  + Add task milestones (meet NPC, reach location, cinematic trigger).

- backend/app/core/quest/runtime.py
  + Support milestone-driven task completion.
  + Log which rule_event completes which milestone.

- system/mc_plugin:
  + Add location + interact + near-NPC triggers for chapter scenes.

## Patch Expectations
- Each flagship chapter:
  - Tasks progress correctly.
  - Branch tasks reflect memory changes.
  - Milestones appear in `/questlog`.

## Risks
- Scene patches missing teleport → breaking location detection.

## Next Phase
Introduce NL-driven task generation for player-generated chapters.

## Verification
- Validate required triggers fire as expected.
- Validate tasks progress upon corresponding rule_event.
- Validate StoryEngine handles events without error.
- Validate TaskRuntime milestone completion.
- Validate StoryGraph progression if applicable.