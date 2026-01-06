# Adjudication Pipeline Vision

## 1. Overview
This document defines the concrete rules, data contracts, and rollout plan for moving the Ideal City adjudication pipeline toward structured, auto-completing CityPhone submissions. The focus is to:
- Standardize every field required by the adjudication spec.
- Introduce the **build capability** score that gates plan generation.
- Constrain the storyline agent prompt so it fills gaps predictably.
- Surface field health directly inside the CityPhone UI.

All changes apply to the backend (`backend/app/core/ideal_city`), the Minecraft plugin (`system/mc_plugin`), and supporting docs under `docs/`.

## 2. Spec Field Matrix
| Field | Type | Required For Build | Field Owner (Current → Target) | CityPhone Panel Mapping | Notes |
|-------|------|--------------------|-------------------------------|-------------------------|-------|
| `narrative` | `str` | Always | Player entry → Player entry | Narrative input modal | Raw submission body, kept outside panels; stored on spec for auditing. |
| `world_constraints` | `List[str]` | >=1 item | Agent auto-fill → Agent auto-fill (player optional) | Vision card "待补充/约束" | Sanitized strings; empty list blocks readiness. |
| `logic_outline` | `List[str]` | >=2 items | Agent heuristics → Agent must ensure coverage | Vision card "执行逻辑" | Show coverage progress; missing entries flagged. |
| `resource_ledger` | `List[str]` | >=2 items | Sparse player input → Agent fill with structured entries | Resources card | Each item must follow `资源项 - 责任人` pattern. |
| `success_criteria` | `List[str]` | >=1 item | Agent guess → Agent derive explicitly | Vision card notes + Status card | Exposed in status tooltip; influences capability score. |
| `risk_register` | `List[str]` | >=1 item | Rarely filled → Agent enforce for all builds | Resources card (new section) | Use `风险: 描述 / 缓解` format; missing list blocks readiness. |
| `risk_notes` | `List[str]` | Optional | Agent → Agent | Internal only | Stays internal; no UI change. |
| `community_requirements` | `List[str]` | Optional | Agent → Agent | Internal only | Inform narrative feedback but not gating. |
| `player_pose` | Struct `{world,x,y,z,yaw,pitch}` | Needed when plan wants location | Player → Player | Location card | Obtained via `/cityphone pose`; absence yields prompt. |
| `location_hint` | `str` | Optional (unless plan requires) | Mixed → Agent refine | Location card | Agent may refine from narrative; blank allowed but lowers capability score. |
| `notes` | `List[str]` | Optional | System → System | Vision notes | Auto-trimmed for panel; no gating. |
| `open_questions` | `List[str]` | Optional | Agent → Agent | Vision/Status cards | Drives blocking reasons; should sync with prompt follow-ups. |
| `plan` (`BuildPlan`) | Complex | Derived | Scheduler → Scheduler | Plan card | Only available when build capability >= threshold and no blocking fields. |

### Responsibility Snapshot
- **Player** must: provide `narrative`, push pose when requested, optionally add resources.
- **Agent** must: guarantee core field coverage, produce structured entries, and emit blocking hints when coverage fails.
- **System** reports: capability score, blocking fields, and plan availability to the UI.

## 3. Build Capability Scoring
Introduce `build_capability` (0-200) to gate `ready_for_build`.

```
build_capability = motivation_score + logic_score
0 <= motivation_score <= 100
0 <= logic_score <= 100
```

### 3.1 Motivation Score
- Source: latest three `narrative` submissions + player actions.
- Baseline calculation:
  - Narrative length & specificity (0-60).
  - Player-triggered updates (`resource_ledger` additions, `/cityphone pose`) (0-25).
  - Responsiveness to agent follow-up (0-15).
- Tiering: `<40` low, `40-70` medium, `>70` high.

### 3.2 Logic Score
- Computed from coverage of core fields `{logic_outline, world_constraints, resource_ledger, success_criteria, risk_register}`.
- Each field contributes an equal slice (20 points each) when:
  - Contains ≥1 non-empty, non-placeholder entry (`TODO`, `待补`, etc. forbidden).
  - Entries match format rules (e.g., resource lines include source/owner).
- Average sum = logic_score.

### 3.3 Decision Rules
- `logic_score < 50` → force `ready_for_build = False`; plan panel lists missing fields.
- Any core field empty → add to `blocking` array; status card highlights the deficiency.
- Motivation tier drives agent obligation:
  1. **High (≥70)**: agent must auto-complete missing fields using context, may leave at most one blocking reason, and must produce actionable items.
  2. **Medium (40-69)**: agent fills `logic_outline` & `world_constraints`; for others adds targeted `follow_up_questions`.
  3. **Low (<40)**: agent refrains from fabricating fields; records prompts in `open_questions` to seek player input.
- `build_capability ≥ 120` **and** no blocking fields → mark `ready_for_build = True` and allow scheduler to proceed.

## 4. Storyline Agent Contract
Update `StoryStateAgent` prompt and parsing logic.

### 4.1 Prompt Requirements
- System prompt must explain the capability formula, coverage expectations, and placeholder ban.
- Agent output JSON must include:
  ```json
  {
    "goals": [],
    "logic_outline": [],
    "resources": [],
    "community_requirements": [],
    "world_constraints": [],
    "risk_notes": [],
    "risk_register": [],
    "success_criteria": [],
    "location_hint": "",
    "follow_up_questions": [],
    "coverage": {
      "logic_outline": true,
      "world_constraints": true,
      "resource_ledger": true,
      "success_criteria": true,
      "risk_register": true
    },
    "motivation_score": 0,
    "blocking": []
  }
  ```
- High motivation (`>=70`) and an empty field → agent fills the field using structured entries before returning.
- Medium motivation -> agent may return empty fields but must add follow-up entries describing the missing information.
- Low motivation -> agent focuses on clarifying questions; does not fabricate resources/risks.
- Every `resource` entry must contain both item and provider/responsible.
- Every `risk_register` entry must follow `风险: 描述 / 缓解`.

### 4.2 Implementation Steps
1. **Prompt Text**: rewrite `_STORY_STATE_SYSTEM_PROMPT` in `story_state_agent.py` to embed new rules.
2. **Stage Prompts**: extend `_STAGE_PROMPTS` so each stage enumerates fields to confirm.
3. **Normalisation**: update `_normalise` to parse new keys (`risk_register`, `success_criteria`, `coverage`, `motivation_score`, `blocking`).
4. **Fallback Logic**: align `_fallback` to produce compliant structure and blocking hints.
5. **Backend Integration**: adjust `StoryStateManager` merge logic so `blocking` fields and scores persist into `StoryState` & `CityPhoneStatePayload`.

## 5. CityPhone UX Updates
- **Vision Card**: display coverage status icons for `logic_outline`, `world_constraints`, `success_criteria`; annotate missing fields (`需补：资源清单`).
- **Resources Card**: show `resource_ledger` entries under "当前清单"; add new section "风险登记" listing `risk_register`; if empty, show blocking message.
- **Location Card**: continue to prompt `/cityphone pose`; include location hint quality message based on agent output.
- **Plan Card**: when blocked, show aggregated `blocking` fields with guidance text; when ready, show build capability score and plan summary.
- **Status Card**: add `build_capability` gauge and detailed motivation/logic breakdown.

### Plugin Changes
- Update `CityPhoneSnapshot` to parse new JSON fields (`build_capability`, `blocking`, coverage flags).
- Extend `CityPhoneUi` builders to render new hints, risk section, and score display.
- Ensure inventory lore stays within display limits; truncate with ellipsis when necessary.

## 6. Backend Adjustments
- Extend `CityPhoneStatePayload` (in `pipeline.py`) with:
  - `build_capability: int`
  - `motivation_score: int`
  - `logic_score: int`
  - `blocking: List[str]`
- Compute scores inside `IdealCityPipeline.cityphone_state` using stored StoryState metrics.
- When handling `submit_narrative`, merge new agent output fields and recalc capability.
- Ensure `ready_for_build` logic mirrors scoring rules and persists to repository.

## 7. Rollout Plan
1. **Schema Update (Week 1)**
   - Update Pydantic models for new fields.
   - Adjust StoryState serialization to store scores and blocking list.
   - Provide migration script for existing JSONL records (default scores to 0, blocking empty).
2. **Agent Prompt & Tests (Week 2)**
   - Rewrite prompt, adapt parser, add unit tests covering high/medium/low motivation cases.
   - Record fixtures verifying placeholder filtering.
3. **Plugin UI (Week 3)**
   - Update snapshot parsing and GUI rendering.
   - Verify with Paper dev server; screenshot new cards.
4. **Docs & Training (Week 3)**
   - Update `CITYPHONE_UI_PLAN.md`, `IDEAL_CITY_TODO.md`, and this document with final contracts.
   - Produce quickstart for narrative authors on new scoring mechanism.
5. **Beta Validation (Week 4)**
   - Run two scenarios: high motivation player and low motivation player.
   - Confirm `/cityphone state` returns expected scores, UI matches, and plan gating works.
6. **Live Rollout (Week 5)**
   - Enable feature flag for full agent scoring.
   - Monitor build queue for unexpected blocks; gather player feedback.

## 8. Verification Checklist
- [ ] Backend returns capability scores and blocking fields.
- [ ] Agent output JSON passes schema validation, no placeholder text stored.
- [ ] CityPhone UI displays coverage hints and risk ledger section.
- [ ] High motivation scenario auto-generates complete spec and unlocks plan.
- [ ] Low motivation scenario surfaces questions instead of fabricated data.
- [ ] Documentation updated and distributed to narrative/design teams.

## 9. Open Questions
- Define precise heuristics for motivation scoring weights (needs data analysis).
- Decide if `risk_register` should ever be optional for certain scenario types.
- Confirm whether capability score should influence broadcast narration tone.

Once these items are resolved, the adjudication pipeline will have a consistent, auditable pathway from player intent to executable build plans with transparent readiness criteria.
