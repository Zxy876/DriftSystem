 

Phase 27 – Tutorial Completion & Free Story Unlock (Post-Tutorial Transition)

Entry Conditions
	•	Phase 26 completed:
	•	NPC interaction trigger tutorial_meet_guide confirmed firing in-game.
	•	Location-based trigger tutorial_reach_checkpoint confirmed firing in-game.
	•	RuleEventBridge → QuestRuntime → StoryEngine pipeline verified end-to-end.
	•	Observed in-game state:
	•	Tutorial can be entered and replayed.
	•	Tutorial tasks can progress correctly.
	•	However:
	•	Tutorial never formally “ends”.
	•	Player remains stuck in tutorial loop.
	•	Free story interaction is not clearly unlocked.

⸻

Goals
	1.	Define a clear, deterministic tutorial completion condition.
	2.	Transition the player out of tutorial mode in a controlled and observable way.
	3.	Cleanly hand off from:
教学引导模式 → 正式剧情循环
	4.	Ensure tutorial logic never interferes with flagship chapters once completed.

⸻

Required Changes

backend — QuestRuntime / Story rules only (NO story rewrite)

1. Tutorial Completion Milestone (NEW)
	•	Introduce a canonical milestone:
	•	tutorial_complete
	•	Completion condition (logical AND):
	•	tutorial_meet_guide
	•	tutorial_reach_checkpoint
	•	one basic player action:
	•	first chat
	•	or first interact_entity
	•	On completion:
	•	Emit:
	•	milestone: tutorial_complete
	•	exit_ready: true
	•	Constraints:
	•	❌ Do NOT add new story beats
	•	❌ Do NOT mutate or auto-heal existing tutorial tasks
	•	❌ Do NOT rely on free-text semantic interpretation

⸻

backend — Content / JSON only

2. Tutorial Exit Scene (NEW, minimal)
	•	Add a lightweight transition scene:
	•	tutorial_exit
	•	Purpose:
	•	Signal formal end of tutorial
	•	Clean up tutorial-specific world state
	•	Must include:
	•	tell (short narrative closure, 1–2 lines)
	•	_scene_cleanup
	•	teleport to hub / main world
(e.g. KunmingLakeHub)
	•	Must NOT include:
	•	❌ New NPCs
	•	❌ New tasks
	•	❌ New triggers
	•	❌ New quest rules

⸻

system/mc_plugin

3. Tutorial Mode → Normal Mode Switch
	•	On receiving:
	•	milestone: tutorial_complete
	•	or exit_ready: true
	•	PlayerSessionManager switches:
	•	from TUTORIAL / AI_CHAT
	•	to NORMAL
	•	After switch:
	•	Player input is no longer gated by tutorial logic
	•	Natural language input flows directly into StoryEngine
	•	Player feedback (minimal):
	•	ActionBar or chat:
	•	“教程完成，已进入正式剧情”

4. Prevent Tutorial Re-Entry (Per Player)
	•	Once tutorial_complete is true:
	•	/level flagship_tutorial is:
	•	ignored or
	•	redirected to hub with explanation
	•	Tutorial NPC triggers are disabled for that player only
	•	Constraints:
	•	❌ No global flags
	•	❌ No impact on new players
	•	❌ No server-wide state mutation

⸻

Patch Expectations
	•	End-to-end flow becomes:
	1.	Player enters tutorial
	2.	Meets guide NPC
	3.	Reaches checkpoint
	4.	Performs one basic action
	5.	tutorial_complete fires
	6.	Transition scene plays
	7.	Player arrives in hub
	8.	Free-form story interaction begins
	•	Tutorial does not loop
	•	Flagship chapters are no longer blocked by tutorial state
	•	No regression to Phase 26 behavior

⸻

Explicit Non-Goals (Out of Scope)
	•	❌ New tutorial content
	•	❌ New NPC behavior or animation
	•	❌ AI-driven tutorial dialogue
	•	❌ Story rewrites or branching changes
	•	❌ Global reset or auto-heal mutation
	•	❌ Multiplayer synchronization changes

⸻

Risks
	•	Tutorial completion condition too strict or too loose
	•	Session state not persisted correctly across reconnect
	•	Tutorial cleanup affecting shared world state if not scoped per player

⸻

Verification
	•	Verify tutorial_complete milestone is emitted exactly once
	•	Verify tutorial_exit scene runs automatically
	•	Verify tutorial NPC no longer fires triggers after completion
	•	Verify free story interaction works immediately after exit
	•	Verify flagship chapters load normally and independently

### Verification evidence
- `python -m unittest test_quest_runtime` (backend) now exercises the tutorial guide/checkpoint/chat path and asserts the `tutorial_complete` milestone, exit_ready flag, and exit patch forwarding.
- `python -m unittest test_story_graph` (backend) passes, covering StoryGraph graph progression.
- `mvn -DskipITs test` (system/mc_plugin) succeeds, including `RuleEventBridgeTest` which now checks PlayerSessionManager wiring and tutorial completion messaging.


⸻

 