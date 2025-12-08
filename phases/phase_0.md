# Phase 0 — Infrastructure Stabilization (已完成，一般无需执行)

## Entry Conditions
- STATE.md 标记 Phase 0 已完成
- 后端/插件可运行

## Goals
- 确保基础设施完整：backend、mc_plugin、DSL、WorldPatch

## Allowed Files
- /backend/*
- /system/mc_plugin/*
- /docs/*
- /tools/*

## Forbidden Files
- 无（基础阶段）

## Pseudo Diff (Structure Only)
- 验证 backend 启动
- 验证 mc_plugin 构建
- 验证 DSL Registry 注册
- 验证 WorldPatch 合法性

## Success Flag
- 在 STATE.md 写入：
  - PHASE_0_COMPLETE = true

## Next Phase
- phase_1.md