# Phase 11 – StoryGraph Recommendation HUD

## Entry Conditions
- PHASE_10_COMPLETE = true in docs/STATE.md.

## Scope
Add a visible recommendation UI layer in the Minecraft plugin showing:
- next-level suggestions
- reasons (tags, trajectory alignment)
- quick action commands players can click or type

## Allowed Changes
- system/mc_plugin/src/main/java/.../hud/*
- system/mc_plugin/src/main/java/.../intent/*
- backend/app/api/world_api.py (if UI hook needs data shape tweak)
- docs/STATE.md

## Tasks
1. Add a new HUD class:
   - `RecommendationHud.java`
   - Supports:
     - ActionBar summary
     - Clickable chat messages (JSON component)
     - `/story recommend` command to force-refresh

2. Extend plugin → backend call:
   - GET `/world/story/{player}/recommendations`
   - Parse top-ranked 1–3 recommendations
   - Show:
     ```
     ✨ 推荐下一章：《{title}》
     理由：{reasoning summary}
     点击前往 → 直接进入推荐章节
     ```

3. Add command:
   - `/recommend`
   - Fetches & displays HUD

4. Update STATE.md
   - PHASE_11_COMPLETE = true
   - Add summary: StoryGraph HUD available.

## Output Expectations
- Running `/recommend` in-game shows visually formatted suggestion.
- Exiting a level automatically triggers recommendation HUD.