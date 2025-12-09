# Phase 13 – NPC Dialogue UI & Skin Integration

## Entry Conditions
- PHASE_12_COMPLETE = true in docs/STATE.md.

## Scope
Turn existing NPC behaviors/dialogue into a full interactive UI:
- RPG-style dialogue panel
- Animated typing effect
- Load NPC skins automatically
- Add NPC head/name rendering above entity

## Allowed Changes
- system/mc_plugin/src/main/java/.../npc/*
- system/mc_plugin/src/main/java/.../hud/dialogue/*
- backend/app/core/npc/npc_behavior_engine.py (if metadata needed)
- docs/NPC_SYSTEM.md
- docs/STATE.md

## Tasks
1. Add `DialoguePanel.java`
   - JSON chat → GUI panel
   - supports:
     - `npc_say(npc_id, text)`
     - title + body + choices

2. Extend NPC interaction:
   - right-click NPC → open panel
   - allow “选择分支回应”（optional）

3. Implement Skin Loader:
   - read `scene.npc_skins`
   - auto-apply via Citizens 或自制皮肤渲染器（已自动选择 best-fit method）

4. Add NPC nameplate styling:
   - 显示 “桃子 · 赛道教练”
   - 清晰职业角色感

5. Update STATE.md
   - PHASE_13_COMPLETE = true
   - Document: NPC UI ready.

## Output Expectations
- 玩家右击桃子 → 弹出对话UI
- NPC 皮肤自动加载
- 分支对话可扩展（非强制）