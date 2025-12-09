# Phase 8 – Task Feedback & UX

## Entry Conditions
- PHASE_7_COMPLETE = true in docs/STATE.md.

## Scope
- Improve how task and milestone progress is presented to players,
  leveraging existing QuestRuntime responses and plugin-side chat output.

## Allowed Changes
- backend/app/core/quest/runtime.py
- backend/app/api/world_api.py
- system/mc_plugin/src/main/java/com/driftmc/scene/RuleEventBridge.java
- system/mc_plugin/src/main/java/com/driftmc/story/StoryManager.java
- docs/STATE.md

## Tasks
1. Enhance QuestRuntime responses to:
   - include concise task/milestone titles and short hints.
2. Extend RuleEventBridge to:
   - format quest/milestone messages in a consistent “quest log” style.
3. Optionally add lightweight “current task” recall via chat keyword
   (e.g. “我的任务是什么”).
4. Update STATE.md:
   - Set `PHASE_8_COMPLETE = true`.
   - Describe UX improvements under "Progress – Done".

## Output Expectations
- Players receive clear and non-spammy feedback when tasks progress
  or milestones complete.