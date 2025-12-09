# Phase 20 – First Playable Campaign Assembly

## Entry Conditions
- PHASE_19_COMPLETE = true.
- Flagship 03 / 08 / 12 and emotional weather all functional.
- Generative-level system online.

## Scope
Assemble the first complete narrative campaign of the DriftSystem:
Tutorial → flagship_03 → flagship_08 → flagship_12 → flagship_final

## Allowed Changes
- backend/data/flagship_levels/flagship_final.json (new)  
- backend/app/core/story/story_graph.py (campaign weighting)  
- tutorial_level.json (campaign entry pointer)  
- docs/CAMPAIGN_OVERVIEW.md  
- docs/STATE.md  

## Tasks
1. Create `flagship_final.json`:
   - Branching finale depending on memory flags:
     - face_once → hopeful dawn ending
     - escape_once → night-walk cyclical ending
2. StoryGraph:
   - Add campaign ordering bias:
     - After completing flagship_12, recommend flagship_final with +1.0 weight.
3. Update flagship_03 / 08 / 12:
   - Define `next_major_level` so the campaign is linear by default unless branched.
4. Update tutorial:
   - Add NPC that explains how to begin campaign: “踏入心悦主线”.
5. Add CAMPAIGN_OVERVIEW.md:
   - Narrative arc  
   - Emotional progression  
   - Branch summary  
   - Player agency philosophy  

## Output Expectations
- Campaign is playable from start to finish.
- All cinematics, memory flags, emotional patches, and choices shape the story.
- Replayability increases because different choices → different finales.

## Risk Summary
- Finale cinematics must not break camera control.
- Branch conditions must precisely match memory states.

## Next-Phase Expectation
Phase 21 (if created) will cover analytics, polish, or multi-player narrative synchronization.