

Phase 26 – Restore NPC Interaction & Action-Based Triggers (Playable Story Loop)

Entry Conditions
	•	Phase 25 auto-heal diagnostics complete
	•	Scene system correctly spawns featured NPCs (currently ArmorStand placeholders)
	•	QuestRuntime / rule_event / debug tooling verified via backend tests
	•	In-game issue observed:
	•	NPCs appear as wooden stands
	•	Player cannot interact with NPCs
	•	tutorial / flagship tasks remain pending
	•	Story repeats first beat and never advances

⸻

Goals
	1.	Make NPCs physically interactive in-game (minimum viable interaction).
	2.	Restore the action trigger pipeline:
Player action → Plugin listener → RuleEventBridge → QuestRuntime → StoryEngine.
	3.	Ensure tutorial & flagship chapters can progress without free-text AI guessing.
	4.	Clearly separate:
	•	剧情推进触发（quest_event）
	•	系统指令 / 自由聊天（chat-only）

⸻

Required Changes

system/mc_plugin (primary focus)

1. NPC Interaction Listener (NEW)
	•	Add a listener for:
	•	PlayerInteractAtEntityEvent (right-click NPC)
	•	Optional: proximity trigger via PlayerMoveEvent (radius-based)
	•	Determine whether the clicked entity:
	•	Belongs to the current Scene
	•	Matches featured_npc or npc_triggers metadata

2. Scene → NPC → quest_event Bridge
	•	From Scene metadata:
	•	_scene.featured_npc
	•	_scene.npc_triggers[]
	•	Resolve corresponding canonical quest_event, e.g.:
	•	tutorial_meet_guide
	•	flagship03_meet_npc
	•	Emit event via:
	•	RuleEventBridge.emitQuestEvent(player, quest_event)

3. Player Feedback (Minimal)
	•	ActionBar or chat feedback on trigger:
	•	你与【心悦向导】交谈
	•	Prevent duplicate firing:
	•	Per-NPC cooldown
	•	Or once-only per scene session

⸻

backend (NO major refactor)

4. Ensure Action-Based Events Are Accepted
	•	Verify QuestRuntime already accepts:
	•	quest_event from RuleEventBridge
	•	No changes to StoryEngine logic
	•	No new AI-driven branching

⸻

Content Validation (JSON, no redesign)

5. Scene Metadata Sanity Check
	•	Verify in:
	•	flagship_tutorial.json
	•	flagship_03 / 08 / 12
	•	Each NPC interaction point includes:
	•	npc_triggers
	•	canonical quest_event
	•	No reliance on free-text dialogue to advance tasks

⸻

Patch Expectations
	•	Tutorial chapter becomes playable end-to-end:
	1.	Player enters scene → NPC appears
	2.	Player right-clicks NPC
	3.	tutorial_meet_guide fires
	4.	Quest progress updates in /questlog
	5.	“继续” advances to next beat instead of looping
	•	Flagship chapters no longer stall on NPC-related tasks
	•	NPCs remain simple placeholders (ArmorStand OK)

⸻

Explicit Non-Goals (Out of Scope)
	•	❌ AI free-form NPC dialogue
	•	❌ Citizens / MythicMobs integration
	•	❌ NPC pathfinding or animation
	•	❌ Story rewrites or new beats
	•	❌ Auto-heal mutation of live tasks

⸻

Risks
	•	NPC entity not correctly mapped back to Scene metadata
	•	Multiple listeners firing duplicate

## Verification
- Validate required triggers fire as expected.
- Validate tasks progress upon corresponding rule_event.
- Validate StoryEngine handles events without error.
- Validate TaskRuntime milestone completion.
- Validate StoryGraph progression if applicable.