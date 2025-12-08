# Phase 4 — AI Task System + NPC Logic

## Entry Conditions
- PHASE_3_COMPLETE = true

## Goals
- 完整任务系统（conditions/milestones/rewards）
- NPC 行为由 rulegraph 驱动
- rule-driven task evaluation

## Allowed Files
/backend/app/core/quest/runtime.py  
/backend/app/core/npc/*  
/backend/app/api/world_api.py  

## Forbidden Files
- mc_plugin/*（结构已完成）
- Scene 系统

## Pseudo Diff
+ TaskSession 存储 milestones/rewards
+ QuestRuntime.handle_rule_trigger → update tasks
+ NPC BehaviorEngine 挂钩 rulegraph

## Success Flag
PHASE_4_COMPLETE = true

## Next Phase
phase_5.md