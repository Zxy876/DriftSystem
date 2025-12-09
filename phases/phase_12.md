# Phase 12 – Quest Log HUD & Progress Panel

## Entry Conditions
- PHASE_11_COMPLETE = true in docs/STATE.md.

## Scope
Implement a visible quest log system for:
- active tasks
- milestone progress
- rewards
- remaining conditions

## Allowed Changes
- system/mc_plugin/src/main/java/.../hud/*
- system/mc_plugin/src/main/java/.../quest/*
- backend/app/core/quest/runtime.py (metadata tweaks)
- docs/TUTORIAL_SYSTEM.md
- docs/STATE.md

## Tasks
1. Add `QuestLogHud.java`
   - Bullet list formatting:
     ```
     📘 任务：攀登之路
     - 目标：到达山顶 (1/2)
     - 奖励：🪢 climbing rope
     - 提示：寻找更安全的路径
     ```
   - Supports:
     - `/questlog`
     - auto-refresh on rule_event

2. Runtime → plugin formatting patch:
   - Extend rule-event payload to include `remaining`, `milestone_names`, `task_titles`

3. Add HUD triggers:
   - 玩家进入/退出关卡
   - 完成 milestone 时自动弹出进度条/ActionBar

4. Update STATE.md
   - PHASE_12_COMPLETE = true
   - QuestLog UI available.

## Output Expectations
- Player runs `/questlog` → sees formatted structured quest log
- Finishing a milestone → ActionBar 更新