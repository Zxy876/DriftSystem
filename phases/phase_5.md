# Phase 5 — Mainline Exit System（昆明湖主线）

## Entry Conditions
- PHASE_4_COMPLETE = true

## Goals
- Exit 意图 → end_story → cleanup → teleport KunmingLakeHub
- 主线任务：观察、收集、记录
- StoryGraph 记录叙事轨迹

## Allowed Files
/system/mc_plugin/src/main/java/com/driftmc/exit/*  
/backend/app/core/story/story_engine.py  
/backend/app/api/world_api.py  

## Forbidden Files
- beat/task/scene 系统（已完成）

## Pseudo Diff
+ ExitIntentDetector（mc 插件）
+ story_engine.exit_level_with_cleanup → teleport hub
+ StoryGraph.updateTrajectory()

## Success Flag
PHASE_5_COMPLETE = true

## Next Phase
- DONE (宇宙上线)