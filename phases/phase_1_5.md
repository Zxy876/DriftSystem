# Phase 1.5 — Narrative+Scene+Rules+Tasks+Exit Scaffold

## Entry Conditions
- PHASE_1_COMPLETE = true
- STATE.md 当前 Phase = 1.5

## Goals
建立五层结构骨架，不要求逻辑完整：
- beats skeleton
- scene skeleton
- rules skeleton
- tasks skeleton
- exit skeleton
- StoryEngine/QuestRuntime/world_api hooks

## Allowed Files
/docs/LEVEL_FORMAT.md  
/backend/app/core/story/level_schema.py  
/backend/app/core/story/story_engine.py  
/backend/app/core/quest/runtime.py  
/backend/app/api/world_api.py  

## Forbidden Files
- mc_plugin/*
- 深层逻辑
- Beat 运行时逻辑

## Pseudo Diff
（此内容是已经由你与 Copilot 实现的部分，仅原样提供 skeleton）
+ level_schema 添加 beats/scene/rules/tasks/exit
+ StoryEngine 添加：enter_level_with_scene / inject_tasks / register_rule_listeners / exit_level_with_cleanup / advance_with_beat
+ QuestRuntime 添加 rule-listener storage
+ world_api 添加 /story/enter /story/end /story/rule-event

## Success Flag
PHASE_1_5_COMPLETE = true

## Next Phase
phase_2.md