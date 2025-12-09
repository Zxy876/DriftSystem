# Phase 19 – World Reactivity & Emotional Weather System

## Entry Conditions
- PHASE_18_COMPLETE = true.
- Memory system fully operational.

## Scope
Make the Minecraft world react to player emotional state (memory flags + choices):
- Weather transitions.
- Lighting shifts.
- Music changes.
- NPC tone adjustments.

## Allowed Changes
- backend/app/core/story/story_engine.py  
- backend/app/api/world_api.py  
- system/mc_plugin/src/main/java/com/driftmc/scene/SceneAwareWorldPatchExecutor.java  
- system/mc_plugin/src/main/java/com/driftmc/npc/NPCManager.java  
- flagship level JSONs (emotional_world_patch fields)  
- docs/EMOTIONAL_WEATHER.md  
- docs/STATE.md  

## Tasks
1. Add emotional_world_patch pipeline:
   - After each beat, StoryEngine sends world_patch influenced by memory flags.
   - Example:
     - xinyue.face_once → CLEAR_SKY, warm particles, hopeful music.
     - xinyue.escape_once → RAIN, low light, echo footsteps.
2. NPC adaptive dialogue:
   - NPCManager reads emotional state and adjusts lines:
     - Encouraging if facing.
     - Reserved if escaping.
3. Add `/world/story/{player}/emotional-weather` endpoint for debugging.
4. Implement hub-reactivity:
   - Hub NPCs change lines as the player's arc evolves.

## Output Expectations
- Player feels: “世界在读我，而不是我在读世界。”
- Weather, lighting, sounds, and NPC tone shift based on choices.
- Beats with memory_required automatically invoke emotional world patches.

## Risk Summary
- Too aggressive changes can cause nausea or visual conflict with Minecraft limitations.
- Emotional patch must not override active cinematics.

## Next-Phase Expectation
Phase 20 builds the first full playable campaign using these systems.