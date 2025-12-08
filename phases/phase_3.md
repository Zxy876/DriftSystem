# Phase 3 — Scene Generation & Cleanup

## Entry Conditions
- PHASE_2_COMPLETE = true

## Goals
- 进入关卡 → 加载 scene
- 退出关卡 → 清理 scene
- 不污染世界（全部反向 patch）

## Allowed Files
/system/mc_plugin/src/main/java/com/driftmc/scene/*  
/backend/app/core/story/story_engine.py  
/backend/app/api/world_api.py  

## Forbidden Files
- beats 逻辑
- tasks 系统
- QuestRuntime 内部结构

## Pseudo Diff
+ SceneLoader.loadScene()
+ SceneCleanupService.cleanupScene()
+ RuleEventBridge 将 mc 事件转发到 backend

## Success Flag
PHASE_3_COMPLETE = true

## Next Phase
phase_4.md