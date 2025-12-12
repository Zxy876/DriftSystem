# Phase 21 – Repair Tutorial Tasks & Reconnect Trigger System

## Entry Conditions
- Phase 20 flagship migration complete
- tutorial loads flagship_tutorial.json
- tasks in tutorial cannot complete in-game

## Goals
1. Make all tutorial tasks finishable.
2. Restore the trigger pipeline:
   Player behavior → RuleEventBridge → TaskRuntime → StoryEngine.
3. Replace all legacy triggers (`level_01`, `tutorial_level`) with canonical flagship triggers.

## Required Changes
- backend/app/core/story/story_loader.py
  + Register legacy tutorial IDs to canonical "flagship_tutorial".
- backend/app/core/story/level_schema.py
  + Ensure TaskConfig includes: `rule_event`, `memory_set`, `conditions`.
- backend/app/core/quest/runtime.py
  + Add canonical event names:
      tutorial_intro_started
      tutorial_meet_guide
      tutorial_reach_checkpoint
      tutorial_task_complete
- backend/data/flagship_levels/flagship_tutorial.json
  + Replace ALL old task rule_event names with canonical ones.
  + Add scene-based triggers for guide NPC & checkpoint approach.

- system/mc_plugin:
  + NPCManager: fire `tutorial_meet_guide` on right-click.
  + WorldPatchExecutor: emit location triggers when entering checkpoint radius.
  + SceneAwareWorldPatchExecutor: ensure tutorial scene emits entry trigger.

## Patch Expectations
- Tutorial task automatically completes when:
  1) Player meets guide NPC,
  2) Player walks through checkpoint,
  3) Player performs the tutorial action (chat or interact).

## Risks
- Incorrect rule_event alias mapping
- Missing canonicalization inside IntentDispatcher2

## Next Phase
Fix tasks in *flagship_03 / 08 / 12 / final*.

## Verification
- Validate required triggers fire as expected.
- Validate tasks progress upon corresponding rule_event.
- Validate StoryEngine handles events without error.
- Validate TaskRuntime milestone completion.
- Validate StoryGraph progression if applicable.