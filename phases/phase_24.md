# Phase 24 – Task Debugging Tools

## Entry Conditions
- Generated tasks & flagship tasks are functional
- We need visibility into which task is stuck

## Goals
1. Add debug mode to inspect task state.
2. Add endpoint:
      GET /world/story/{player_id}/debug/tasks
3. Add in-game command `/taskdebug` to show live task status.

## Required Changes
- backend/app/api/world_api.py
  + Implement /debug/tasks returning:
      active_tasks
      completed_milestones
      pending_conditions
      last_rule_event

- backend/app/core/quest/runtime.py
  + Add instrumentation for milestone and rule event matching.

- system/mc_plugin:
  + Add `/taskdebug` command with action-bar overlay showing:
      - current active task
      - pending milestones
      - last received event
      - whether event matched any task

## Patch Expectations
- Developer can instantly know “为什么任务没有完成”.
- No more blind debugging.

## Risks
- Must hide debug mode from regular players.

## Verification
- Validate required triggers fire as expected.
- Validate tasks progress upon corresponding rule_event.
- Validate StoryEngine handles events without error.
- Validate TaskRuntime milestone completion.
- Validate StoryGraph progression if applicable.