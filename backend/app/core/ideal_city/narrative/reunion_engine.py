from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from app.core.ai.deepseek_agent import call_deepseek
from app.core.ideal_city.ai_settings import AI_CONNECT_TIMEOUT, AI_READ_TIMEOUT
from app.core.ideal_city.story_state import StoryStatePatch

from .types import NarrativeRuntimeContext

logger = logging.getLogger(__name__)

WORLD_PROMPT_VERSION = "reunion_v1"
NARRATIVE_DENSITY = str(os.getenv("NARRATIVE_DENSITY", "low")).strip().lower() or "low"

_DENSITY_TOKEN_BUDGET = {
    "low": 640,
    "medium": 760,
    "high": 880,
}

_CONTINUATION_SIGNALS = (
    "继续",
    "接着",
    "然后",
    "下一步",
    "再",
    "go on",
    "continue",
    "next",
)

_SCENE_CONTEXT_SIGNALS = (
    "新场景",
    "换到",
    "进入",
    "回到",
    "附近",
    "入口",
    "在",
)


def build_reunion_prompt(_context: NarrativeRuntimeContext) -> str:
    return """
Drift World Narrative Engine

Reunion World Protocol

Identity

You are the narrative engine of a persistent Minecraft world.

This world exists because three young people, who grew up together under similar forms of intense training, have chosen to meet again.

They do not return to compete.
They do not return to prove.

They return to create.

Background of the World

The three participants once lived inside systems that valued results, discipline, and proof.

Over time, they realised something else had been fading:
- unfinished conversations
- shared silence
- hesitation before decision
- the feeling of building something without needing it to win

They enter this world not to reconstruct the past,
but to build something together without urgency.

This world is their shared space.

Core World Laws
1. Language can change the world.
2. The world responds, but does not dominate.
3. No one is required to finish anything.
4. Imported fragments become part of the shared structure.
5. The world remembers states across sessions.

Narrative Behaviour

You may:
- extend a scene gently
- add environmental detail
- respond to intention
- allow threads to develop

You must not:
- force emotional resolution
- summarise meaning
- assign moral interpretation
- create dramatic climax unless invited

Push narrative only when participants signal continuation.
Otherwise, maintain space.

Tone Guidelines
- Keep responses grounded.
- Avoid grand declarations.
- Avoid excessive symbolism.
- Preserve ambiguity.
- Let meaning emerge from interaction.

The world is not a stage.
It is a place being used.

Collaboration Principle

The three participants are equals.

No single voice dominates.

If they disagree, the world may reflect tension subtly,
but never escalate it artificially.

Creation is the goal,
not conclusion.

Ending Rule

The world does not end stories.

Participants may leave,
but the world remains available.

Return JSON only with optional keys from this patch schema:
{
  "goals": ["..."],
  "logic_outline": ["..."],
  "resources": ["资源项 - 责任人"],
  "community_requirements": ["..."],
  "world_constraints": ["..."],
  "risk_notes": ["..."],
  "risk_register": ["风险: 描述 / 缓解"],
  "success_criteria": ["..."],
  "location_hint": "...",
  "follow_up_questions": ["..."]
}
Keep outputs concise and stable. Avoid long monologues.
""".strip()


class ReunionNarrativeEngine:
    def infer(self, context: NarrativeRuntimeContext) -> StoryStatePatch:
        runtime_context = self._build_runtime_context(context)
        push_trigger_reason = self._push_trigger_reason(context)
        allow_push = push_trigger_reason is not None

        system_prompt = (
            f"{build_reunion_prompt(context)}\n\n"
            f"WORLD_PROMPT_VERSION={WORLD_PROMPT_VERSION}\n"
            f"NARRATIVE_DENSITY={NARRATIVE_DENSITY}\n"
            f"allow_scene_extension={allow_push}\n"
            f"push_trigger_reason={push_trigger_reason or 'none'}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(runtime_context, ensure_ascii=False)},
        ]

        response = call_deepseek(
            runtime_context,
            messages,
            temperature=self._temperature_for_density(),
            connect_timeout=AI_CONNECT_TIMEOUT,
            read_timeout=AI_READ_TIMEOUT,
            max_tokens=self._max_tokens_for_density(),
        )

        raw = response.get("parsed") if isinstance(response, dict) else None
        if not isinstance(raw, dict):
            logger.debug(
                "narrative_response",
                extra={
                    "narrative_mode": "reunion",
                    "prompt_version": WORLD_PROMPT_VERSION,
                    "response_token_count": 0,
                    "push_trigger_reason": push_trigger_reason,
                },
            )
            return StoryStatePatch()

        response_token_count = self._estimate_token_count(raw)
        logger.debug(
            "narrative_response",
            extra={
                "narrative_mode": "reunion",
                "prompt_version": WORLD_PROMPT_VERSION,
                "response_token_count": response_token_count,
                "push_trigger_reason": push_trigger_reason,
            },
        )

        patch = self._normalise(raw)
        return self._apply_density_controls(patch, allow_push=allow_push)

    def _normalise(self, raw: Dict[str, Any]) -> StoryStatePatch:
        def _list(key: str) -> Optional[List[str]]:
            value = raw.get(key)
            if not isinstance(value, list):
                return None
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            return cleaned or None

        location_hint = raw.get("location_hint") if isinstance(raw.get("location_hint"), str) else None
        if isinstance(location_hint, str):
            location_hint = location_hint.strip() or None

        return StoryStatePatch(
            goals=_list("goals"),
            logic_outline=_list("logic_outline"),
            resources=_list("resources"),
            community_requirements=_list("community_requirements"),
            world_constraints=_list("world_constraints"),
            risk_notes=_list("risk_notes"),
            risk_register=_list("risk_register"),
            success_criteria=_list("success_criteria"),
            location_hint=location_hint,
            follow_up_questions=_list("follow_up_questions"),
        )

    def _build_runtime_context(self, ctx: NarrativeRuntimeContext) -> Dict[str, object]:
        player_input = (ctx.narrative or "").strip()
        scene_hint = _infer_location_hint(player_input) or ctx.existing_state.location_hint
        world_state: Dict[str, object] = {
            "ready_for_build": bool(ctx.existing_state.ready_for_build),
            "open_questions_count": len(ctx.existing_state.open_questions or []),
            "blocking_count": len(ctx.existing_state.blocking or []),
        }
        active_scene: Dict[str, object] = {
            "scenario_id": ctx.scenario.scenario_id,
            "location_hint": scene_hint,
        }
        runtime_context: Dict[str, object] = {
            "world_state": world_state,
            "active_scene": active_scene,
            "player_input": player_input,
            "recent_history_summary": self._summarise_recent_history(ctx),
        }
        if ctx.existing_state.motivation_score:
            runtime_context["emotion_state"] = {
                "motivation_score": int(ctx.existing_state.motivation_score),
                "mood": self._mood_from_score(ctx.existing_state.motivation_score),
            }
        return runtime_context

    def _summarise_recent_history(self, ctx: NarrativeRuntimeContext) -> str:
        notes = [line.strip() for line in (ctx.existing_state.notes or []) if isinstance(line, str) and line.strip()]
        recent = notes[-3:]
        summary = " / ".join(recent)
        if len(summary) > 220:
            summary = summary[:217] + "..."
        return summary or "暂无历史摘要"

    def _push_trigger_reason(self, ctx: NarrativeRuntimeContext) -> Optional[str]:
        player_input = (ctx.narrative or "").strip().lower()
        has_continuation = any(signal in player_input for signal in _CONTINUATION_SIGNALS)
        is_idle = self._scene_structurally_idle(ctx)
        has_new_scene_context = self._introduces_new_scene_context(ctx)
        if has_continuation and is_idle and has_new_scene_context:
            return "continuation+idle+new_scene_context"
        return None

    def _scene_structurally_idle(self, ctx: NarrativeRuntimeContext) -> bool:
        state = ctx.existing_state
        return bool(state.ready_for_build) or (
            len(state.open_questions or []) == 0 and len(state.blocking or []) == 0
        )

    def _introduces_new_scene_context(self, ctx: NarrativeRuntimeContext) -> bool:
        text = (ctx.narrative or "").strip()
        lowered = text.lower()
        hint = _infer_location_hint(text)
        if hint and hint != (ctx.existing_state.location_hint or ""):
            return True
        return any(token in lowered for token in _SCENE_CONTEXT_SIGNALS)

    def _temperature_for_density(self) -> float:
        if NARRATIVE_DENSITY == "high":
            return 0.45
        if NARRATIVE_DENSITY == "medium":
            return 0.3
        return 0.2

    def _max_tokens_for_density(self) -> int:
        return int(_DENSITY_TOKEN_BUDGET.get(NARRATIVE_DENSITY, 640))

    def _estimate_token_count(self, payload: Dict[str, Any]) -> int:
        text = json.dumps(payload, ensure_ascii=False)
        return max(1, len(text) // 4)

    def _mood_from_score(self, score: int) -> str:
        if score >= 80:
            return "steady"
        if score >= 50:
            return "tentative"
        return "uncertain"

    def _apply_density_controls(self, patch: StoryStatePatch, *, allow_push: bool) -> StoryStatePatch:
        if NARRATIVE_DENSITY == "high":
            max_items = 4 if allow_push else 2
        elif NARRATIVE_DENSITY == "medium":
            max_items = 3 if allow_push else 2
        else:
            max_items = 2 if allow_push else 1

        def _cap(values: Optional[List[str]]) -> Optional[List[str]]:
            if not values:
                return values
            capped = [str(item).strip() for item in values if str(item).strip()][:max_items]
            return capped or None

        return patch.model_copy(
            update={
                "goals": _cap(patch.goals),
                "logic_outline": _cap(patch.logic_outline),
                "resources": _cap(patch.resources),
                "community_requirements": _cap(patch.community_requirements),
                "world_constraints": _cap(patch.world_constraints),
                "risk_notes": _cap(patch.risk_notes),
                "risk_register": _cap(patch.risk_register),
                "success_criteria": _cap(patch.success_criteria),
                "follow_up_questions": _cap(patch.follow_up_questions),
            }
        )


def _infer_location_hint(text: str) -> Optional[str]:
    pattern = re.compile(r"在(?P<place>[\u4e00-\u9fffA-Za-z0-9\s]{1,24}?)(?:旁|附近|内|里|周边|入口|附近)")
    match = pattern.search(text)
    if match:
        return f"{match.group('place').strip()}附近"
    pattern = re.compile(r"放在(?P<place>[\u4e00-\u9fffA-Za-z0-9\s]{1,24})")
    match = pattern.search(text)
    if match:
        return f"{match.group('place').strip()}"
    return None
