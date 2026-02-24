from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.ai.deepseek_agent import call_deepseek
from app.core.ideal_city.ai_settings import AI_CONNECT_TIMEOUT, AI_READ_TIMEOUT
from app.core.ideal_city.story_state import StoryStatePatch

from .types import NarrativeRuntimeContext

logger = logging.getLogger(__name__)

WORLD_PROMPT_VERSION = "ideal_city_v1"


def build_ideal_city_prompt(_context: NarrativeRuntimeContext) -> str:
    return """
你是理想之城 adjudication pipeline 的 StoryStateAgent，负责把玩家叙述转成完整的审查档案。
仅返回 JSON，字段允许：
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
  "protocol_state": {
    "completeness_state": {},
    "protocol_flags": {}
  }
}
规则：
- resources 使用 “资源项 - 责任人” 格式。
- risk_register 使用 “风险: 描述 / 缓解” 格式。
- 如果缺口明显，使用 follow_up_questions 提问。
""".strip()


class IdealCityNarrativeEngine:
    def infer(self, context: NarrativeRuntimeContext) -> StoryStatePatch:
        payload = {
            "narrative": context.narrative,
            "spec": {
                "intent": context.spec.intent_summary,
                "logic_outline": context.spec.logic_outline,
                "resources": context.spec.resource_ledger,
                "success": context.spec.success_criteria,
            },
            "scenario": {
                "id": context.scenario.scenario_id,
                "title": context.scenario.title,
                "problem": context.scenario.problem_statement,
                "constraints": context.scenario.contextual_constraints,
            },
            "existing_state": context.existing_state.model_dump(mode="json"),
        }

        messages = [
            {"role": "system", "content": build_ideal_city_prompt(context)},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        response = call_deepseek(
            payload,
            messages,
            temperature=0.2,
            connect_timeout=AI_CONNECT_TIMEOUT,
            read_timeout=AI_READ_TIMEOUT,
        )

        raw = response.get("parsed") if isinstance(response, dict) else None
        if not isinstance(raw, dict):
            logger.debug(
                "narrative_response",
                extra={
                    "narrative_mode": "ideal_city",
                    "prompt_version": WORLD_PROMPT_VERSION,
                },
            )
            return StoryStatePatch(
                protocol_state={
                    "completeness_state": {},
                    "protocol_flags": {"fallback_used": True},
                }
            )

        logger.debug(
            "narrative_response",
            extra={
                "narrative_mode": "ideal_city",
                "prompt_version": WORLD_PROMPT_VERSION,
            },
        )
        return self._normalise(raw)

    def _normalise(self, raw: Dict[str, Any]) -> StoryStatePatch:
        def _list(key: str) -> Optional[List[str]]:
            values = raw.get(key)
            if not isinstance(values, list):
                return None
            cleaned = [str(item).strip() for item in values if str(item).strip()]
            return cleaned or None

        location_hint = raw.get("location_hint")
        if not isinstance(location_hint, str):
            location_hint = None
        else:
            location_hint = location_hint.strip() or None

        protocol_state = raw.get("protocol_state")
        if not isinstance(protocol_state, dict):
            protocol_state = {
                "completeness_state": {},
                "protocol_flags": {},
            }
        else:
            protocol_state = {
                "completeness_state": protocol_state.get("completeness_state")
                if isinstance(protocol_state.get("completeness_state"), dict)
                else {},
                "protocol_flags": protocol_state.get("protocol_flags")
                if isinstance(protocol_state.get("protocol_flags"), dict)
                else {},
            }

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
            protocol_state=protocol_state,
        )
