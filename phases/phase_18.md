# Phase 18 – Generative Level Authoring (User-Created Flagship Chapters)

## Entry Conditions
- PHASE_17_COMPLETE = true.
- flagship_levels is the active story directory.
- StoryEngine supports memory and branching.

## Scope
Add a fully functional natural-language → level generator:
- Players can describe a scene.
- Backend synthesizes a playable flagship-format level JSON.
- Generated levels behave like any authored flagship chapter.

## Allowed Changes
- backend/app/api/level_api.py  
- backend/app/core/story/story_engine.py  
- backend/app/core/story/story_loader.py  
- backend/app/core/story/story_graph.py (preference weights for generated content)  
- backend/enhance_generated_level.py (new helper module)  
- docs/GEN_LEVEL_SYSTEM.md  
- docs/STATE.md  

## Tasks
1. Add POST `/world/story/generate-level` endpoint:
   - Input: natural language description.
   - Output: complete level JSON matching flagship schema.
   - Save to: `backend/data/flagship_levels/generated/flagship_user_<timestamp>.json`
2. Auto-generate:
   - `scene` block with teleport, weather, structures.
   - 1–3 beats with emotions + optional choices.
   - Optional cinematic or memory flags.
   - Exit block.
3. Add StoryGraph integration:
   - “User-generated interest signal” boosts recommended levels with similar tags.
4. Add GEN_LEVEL_SYSTEM.md documentation:
   - JSON contract.
   - Example input → generated level.

## Output Expectations
- Player can type “我想写一个关于月亮下的桥的关卡” → receives a playable level.
- StoryEngine loads generated level without restart.
- Generated chapters appear in StoryGraph recommendations.

## Risk Summary
- Incorrect schema could break runtime loading.
- Player-generated content must never override flagship ids.
- Generator must sanitize text and missing fields.

## Next-Phase Expectation
Phase 19 introduces emotional world reactivity and dynamic environmental response.