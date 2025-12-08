# Phase 2 — Beat-driven StoryEngine

## Entry Conditions
- PHASE_1_5_COMPLETE = true

## Goals
- 实现 beat → world patch
- beat → rule activation
- beat → tasks update
- event_manager → beat advancement

## Allowed Files
/backend/app/core/story/story_engine.py  
/backend/app/core/story/level_schema.py  
/backend/app/core/events/event_manager.py  
/backend/app/core/quest/runtime.py  

## Forbidden Files
- /system/mc_plugin/*
- 场景加载/退出逻辑（属于 Phase 3）

## Pseudo Diff
+ story_engine.advance 使用 beat.trigger
+ 加载 beat.scene_patch → emit world patch
+ 注册 beat.rule_refs → QuestRuntime 激活规则
+ event_manager 监听 near/interact/item_use → 调 advance()
+ QuestRuntime 可触发 beat 催化（rule-driven）

## Success Flag
PHASE_2_COMPLETE = true

## Next Phase
phase_3.md