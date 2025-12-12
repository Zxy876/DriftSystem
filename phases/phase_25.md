# Phase 25 – Autonomous Task Self-Healing System

## Entry Conditions
- Task debugging tools exist
- We know which events fail

## Goals
1. Automatically detect when a task should have progressed but didn’t.
2. Log “orphan rule_event” with suggested fix.
3. Auto-heal simple mismatches by:
   - inferring likely correct rule_event
   - rewriting the active task listener in memory

## Required Changes
- backend/app/core/quest/runtime.py
  + Add anomaly detection:
       If rule_event received AND
          no task matches it AND
          player is inside a valid scene
       → mark as orphan

- story_engine.py
  + Provide minimal "in-memory patch" for tasks:
       If title or tags match, auto-map rule_event

- docs/TASK_AUTOFIX.md
  + Document how self-healing works

## Patch Expectations
- Tasks never “卡死”.
- System always provides a diagnostic & proposed patch.
- Copilot can read the suggestion and auto-generate the PR.

## Risks
- Over-aggressive healing might match the wrong rule_event.

## Verification
- Validate required triggers fire as expected.
- Validate tasks progress upon corresponding rule_event.
- Validate StoryEngine handles events without error.
- Validate TaskRuntime milestone completion.
- Validate StoryGraph progression if applicable.