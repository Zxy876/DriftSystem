 
⸻

Phase 28 – Tutorial Playability & Safety UX (First-Time Player Experience Polish)

Entry Conditions
	•	Phase 27 completed:
	•	tutorial_complete milestone is emitted deterministically.
	•	Tutorial exit scene (tutorial_exit) runs automatically.
	•	Player is transitioned from TUTORIAL / AI_CHAT to NORMAL mode.
	•	Tutorial re-entry is blocked per player.
	•	Observed in-game state:
	•	Tutorial flow is functionally correct and completable.
	•	NPC interaction and checkpoint triggers fire reliably.
	•	However:
	•	Tutorial platform is easy to fall from.
	•	Players frequently die during teaching moments.
	•	Near/NPC prompts and scene rebuilds feel repetitive.
	•	Early experience causes confusion or frustration instead of guidance.

⸻

Goals
	1.	Prevent accidental player death during the tutorial.
	2.	Reduce frustration caused by repeated prompts and scene resets.
	3.	Improve clarity of “what to do next” without adding new content.
	4.	Preserve all existing tutorial logic, tasks, and story structure.
	5.	Ensure post-tutorial free play remains untouched.

⸻

Required Changes

system/mc_plugin — Tutorial Safety Layer (Minimal, Non-Invasive)

1. Tutorial Fall Protection (NEW)
	•	While player session mode is TUTORIAL:
	•	Prevent death from falling off tutorial platforms.
	•	Acceptable implementations (choose ONE):
	•	Temporary no-fall-damage flag.
	•	Auto-teleport player back to tutorial anchor if Y drops below threshold.
	•	Slow-fall or levitation effect applied only in tutorial scene.
	•	Constraints:
	•	❌ No global gamerule changes.
	•	❌ No impact on non-tutorial scenes.
	•	❌ No permanent potion effects.

⸻

2. Tutorial Respawn Stabilization
	•	If player dies during tutorial:
	•	Respawn location must be:
	•	tutorial teleport anchor
	•	or safe tutorial platform
	•	Must NOT:
	•	Restart tutorial tasks.
	•	Re-fire tutorial intro beats.
	•	Duplicate NPC spawns.

⸻

system/mc_plugin — Interaction & Prompt Throttling

3. Near / NPC Prompt De-duplication
	•	For tutorial NPCs:
	•	Near-based prompts should:
	•	Fire once per logical step.
	•	Be suppressed after interaction has occurred.
	•	Prevent:
	•	Repeated “靠近了心悦向导” loops.
	•	Re-triggering identical narration nodes.
	•	Implementation hint:
	•	Per-player, per-scene memory flag
	•	Reset only on tutorial restart (new player)

⸻

4. Scene Cleanup Noise Reduction
	•	Avoid unnecessary:
	•	_scene_cleanup
	•	platform rebuilds
	•	repeated spawn/despawn cycles
	•	Tutorial scene should feel:
	•	Stable
	•	Continuous
	•	Not “resetting” unless explicitly exiting

⸻

Patch Expectations
	•	First-time tutorial experience becomes:
	1.	Player enters tutorial safely.
	2.	Player can explore without fear of falling to death.
	3.	NPC guidance feels responsive, not spammy.
	4.	Player clearly understands:
	•	where to go
	•	what to interact with
	5.	Tutorial completes smoothly and hands off to free story.
	•	No regression to Phase 26 or Phase 27 behavior.
	•	No change to tutorial content, tasks, or narrative.

⸻

Explicit Non-Goals (Out of Scope)
	•	❌ New tutorial story content.
	•	❌ New NPC dialogue trees.
	•	❌ New quests or milestones.
	•	❌ Combat balancing.
	•	❌ Global movement or damage changes.
	•	❌ Multiplayer fairness tuning.

⸻

Risks
	•	Over-aggressive safety logic might leak into non-tutorial scenes.
	•	Poorly scoped fall protection could mask legitimate player actions.
	•	Prompt throttling too strict could hide necessary guidance.

⸻

Verification
	•	Verify player cannot permanently die from falling during tutorial.
	•	Verify tutorial respawn returns player to a safe state.
	•	Verify NPC near/interact prompts do not spam repeatedly.
	•	Verify tutorial tasks and milestones still progress normally.
	•	Verify post-tutorial gameplay remains unchanged.

⸻

Verification Evidence (to be filled after completion)
	•	In-game manual tutorial run without death loops.
	•	Plugin-side tests or logs confirming tutorial-only safety logic.
	•	Regression check of flagship chapters and hub free play.

⸻

 