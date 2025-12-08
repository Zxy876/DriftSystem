# Phase 1 — Unified Level Format (已完成)

## Entry Conditions
- PHASE_0_COMPLETE = true
- STATE.md 标记当前 Phase = 1

## Goals
- heart_levels JSON 统一格式
- story_loader/stoy_graph 可解析 Level 基础结构

## Allowed Files
/backend/app/core/story/story_loader.py  
/backend/app/core/story/story_graph.py  
/docs/LEVEL_FORMAT.md  

## Forbidden Files
- mc_plugin/*
- Scene 系统
- Rules/Tasks 系统

## Pseudo Diff
+ 标准化 Level JSON
+ story_loader 加载 id, narrative, world_patch
+ StoryGraph 支持 level_xx → next level 推断

## Success Flag
PHASE_1_COMPLETE = true

## Next Phase
phase_1_5.md