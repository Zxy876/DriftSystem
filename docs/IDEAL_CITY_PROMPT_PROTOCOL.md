# Ideal City Prompt Protocol Alignment

## Purpose
Translate the paper-sourced methodology into actionable engineering steps for the Ideal City pipeline. The target is to remove hard-coded judgement logic and let scenarios and player submissions govern the loop.

## Non-Negotiable Guardrails
- No new intelligent modules or feature surface area.
- Eliminate implicit default patches in code paths.
- Move completeness decisions out of Python conditionals and into scenario configuration.
- StoryState and guidance agents execute the scenario protocol; they do not reinterpret it.

## Scenario-as-Protocol Model
- **Scenario** defines the protocol contract.
- `required_sections` becomes the canonical list of fields a submission must cover.
- Coverage/completeness is computed strictly against this list.
- When a field is missing, the system asks the player to supply it; it never auto-fills.

## Methodological Mapping
1. **Pre-train, Prompt, and Predict**
   - Prompt format == task protocol.
   - Completion status derives solely from protocol compliance.
   - Action: remove default success/logic patches in `spec_normalizer` and related helpers.
2. **Chain-of-Thought Prompting**
   - Require players to submit reasoning/step structures.
   - Adjudication validates the presence and self-consistency of these structures.
   - Guidance focuses on eliciting missing structural elements, not solutions.
3. **ReAct Loop**
   - StoryState = thought snapshot (what is missing).
   - Guidance agent issues one targeted question per missing section.
   - Player response updates state; loop continues until protocol is satisfied.
4. **Self-Consistency (optional)
   - Multiple parses of the same submission can be compared for coverage stability.
   - Choose the parse that maximises `required_sections` coverage with minimal blocking.

## Immediate Experiment: Spec Normalizer
- **Scope**: single scenario (balloon showcase) for controlled validation.
- **Change**: delete heuristic default fillers in `spec_normalizer`.
- **Outcome to observe**: can the player-driven text loop progress without code-injected defaults?

### Steps
1. Add `required_sections` to the balloon showcase scenario.
2. Update completeness checks to rely on scenario metadata.
3. Strip fallback generation of `logic_outline`, `success_criteria`, etc. inside `spec_normalizer`.
4. Run narrative ingestion + device-spec submission tests to confirm flow still converges via player prompts.
5. Document behaviour shifts and decide whether to propagate to other scenarios.

## Testing & Validation
- Run targeted pytest modules: `test_spec_normalizer.py`, `test_story_state_manager.py`, `test_ideal_city_pipeline.py`.
- Manual playtest: simulate CityPhone loop to ensure the guidance agent now asks for missing protocol sections instead of filling them.

## Rollout Notes
- Keep original defaults behind a feature flag if emergency rollback is necessary.
- Update documentation (`PUZZLE_COMMUNITY_ALIGNMENT.md`) once the protocol-driven loop proves stable.
- Plan incremental adoption: spec normalizer → story state agent → guidance prompts.
