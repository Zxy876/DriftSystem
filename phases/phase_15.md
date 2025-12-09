# Phase 15 – Story Choices UI (Player-driven Narrative Branching)

## Entry Conditions
- PHASE_14_COMPLETE = true in docs/STATE.md.

## Scope
Implement a visual novel style branching UI:
- choices
- conditional follow-ups
- StoryGraph recording of selected branch

## Allowed Changes
- system/mc_plugin/src/main/java/.../hud/dialogue/*
- backend/app/core/story/story_engine.py (choice → rule_event)
- backend/app/core/story/story_graph.py
- docs/STORY_BRANCHING.md
- docs/STATE.md

## Tasks
1. Add `ChoicePanel.java`:
   - Buttons:
     ```
     你决定怎么做？
     [1] 跟随桃子训练漂移
     [2] 自己探索赛道
     [3] 追随神秘呼唤
     ```

2. Extend narrative beats:
   - beats support:
     ```
     "choices": [
       { "id": "follow_taozi", "text": "跟随桃子训练", "rule_event": "choice_follow" },
       { "id": "explore", "text": "自己探索", "rule_event": "choice_explore" }
     ]
     ```

3. StoryGraph:
   - log choice
   - adjust future recommendation scores

4. Update STATE.md:
   - PHASE_15_COMPLETE = true
   - Story choices integrated.

## Output Expectations
- 玩家在关键剧情点看到分支界面
- 选择影响故事推荐路径