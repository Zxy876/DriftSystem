# Phase 23 – Natural-Language Task Generation System

## Entry Conditions
- Flagship tasks stable for all chapters
- Players can generate new chapters (Phase 18 system)

## Goals
1. When a player uses `/story/generate-level`, the system must also generate:
   - task list
   - rule_event mapping
   - conditions (explore/interact/reach)
   - milestones

2. Generated tasks must appear in `/questlog` and progress normally.

## Required Changes
- backend/enhance_generated_level.py
  + Add TaskBuilder that infers tasks from NL input.
  + Generate:
      "milestones": [...]
      "tasks": [{"id": "...", "conditions": [...], "rule_event": "..."}]

- backend/app/api/level_api.py
  + After saving new level JSON, call TaskRuntime to register triggers.

- story_graph.py
  + Apply mild recommendation bias for player-created chapters with tasks.

## Patch Expectations
- Generating a level auto-creates tasks aligned with NL description.
- Tasks appear correctly in the HUD.

## Risks
- Poor NL inference → tasks impossible to complete.

## Next Phase
Add task debugging tools for creators.

## Verification
- Validate required triggers fire as expected.
- Validate tasks progress upon corresponding rule_event.
- Validate StoryEngine handles events without error.
- Validate TaskRuntime milestone completion.
- Validate StoryGraph progression if applicable.