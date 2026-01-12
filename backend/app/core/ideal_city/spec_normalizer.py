"""Natural language → structured DeviceSpec normalisation.

This module centralises the parsing responsibility for Ideal City submissions.
It favours AI-assisted extraction via ``call_deepseek`` but always backs off to
local heuristics so guardrails remain deterministic when the AI layer is
unavailable.
"""

from __future__ import annotations

import json
import re
import os
from dotenv import load_dotenv
load_dotenv()
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.ai.deepseek_agent import call_deepseek

from .device_spec import sanitize_lines
from .scenario_repository import ScenarioContext

if TYPE_CHECKING:  # pragma: no cover
    from .pipeline import DeviceSpecSubmission


SPEC_AI_CONNECT_TIMEOUT = float(os.getenv("IDEAL_CITY_SPEC_AI_CONNECT_TIMEOUT", "6.0"))
SPEC_AI_READ_TIMEOUT = float(os.getenv("IDEAL_CITY_SPEC_AI_READ_TIMEOUT", "6.0"))


@dataclass
class NormalizedSpec:
    intent_summary: str
    world_constraints: List[str]
    logic_outline: List[str]
    success_criteria: List[str]
    risk_register: List[str]
    resource_ledger: List[str]
    is_draft: bool = False


class SpecNormalizer:
    """Translate free-form narratives into structured DeviceSpec fields."""

    def normalize(
        self,
        submission: "DeviceSpecSubmission",
        scenario: Optional[ScenarioContext] = None,
    ) -> NormalizedSpec:
        narrative = submission.narrative or ""
        intent_summary = self._summarise_intent(narrative)

        base_lists = {
            "world_constraints": sanitize_lines(submission.world_constraints),
            "logic_outline": sanitize_lines(submission.logic_outline),
            "success_criteria": sanitize_lines(submission.success_criteria),
            "risk_register": sanitize_lines(submission.risk_register),
            "resource_ledger": sanitize_lines(submission.resource_ledger),
        }

        ai_payload = self._run_ai_parser(submission, scenario, intent_summary)
        heuristic_payload = self._heuristic_projection(narrative, scenario, intent_summary)

        player_structured_any = any(base_lists[field] for field in base_lists)

        heuristic_world = heuristic_payload.get("world_constraints") if not player_structured_any else None
        heuristic_logic = heuristic_payload.get("logic_outline") if not player_structured_any else None
        heuristic_success = heuristic_payload.get("success_criteria") if not player_structured_any else None
        heuristic_risk = heuristic_payload.get("risk_register") if not player_structured_any else None
        heuristic_resources = heuristic_payload.get("resource_ledger") if not player_structured_any else None

        world_constraints = self._pick_nonempty(
            base_lists["world_constraints"],
            ai_payload.get("world_constraints"),
            heuristic_world,
        )
        logic_outline = self._pick_nonempty(
            base_lists["logic_outline"],
            ai_payload.get("logic_outline"),
            heuristic_logic,
        )
        success_criteria = self._pick_nonempty(
            base_lists["success_criteria"],
            ai_payload.get("success_criteria"),
            heuristic_success,
        )
        risk_register = self._pick_nonempty(
            base_lists["risk_register"],
            ai_payload.get("risk_register"),
            heuristic_risk,
        )
        resource_ledger = self._pick_nonempty(
            base_lists["resource_ledger"],
            ai_payload.get("resource_ledger"),
            heuristic_resources,
        )

        if ai_payload.get("intent_summary"):
            intent_summary = ai_payload["intent_summary"].strip()

        is_draft = submission.is_draft
        if not is_draft:
            if isinstance(ai_payload.get("is_draft"), bool):
                is_draft = bool(ai_payload.get("is_draft"))
            elif isinstance(ai_payload.get("is_draft"), str):
                is_draft = ai_payload.get("is_draft", "").strip().lower() in {"true", "yes", "1"}
        if not is_draft:
            if isinstance(heuristic_payload.get("is_draft"), bool):
                is_draft = bool(heuristic_payload.get("is_draft"))
        if not is_draft:
            narrative_lower = (submission.narrative or "").lower()
            if "draft" in narrative_lower or "草稿" in narrative_lower:
                is_draft = True

        return NormalizedSpec(
            intent_summary=intent_summary,
            world_constraints=world_constraints,
            logic_outline=logic_outline,
            success_criteria=success_criteria,
            risk_register=risk_register,
            resource_ledger=resource_ledger,
            is_draft=is_draft,
        )

    # ---------------------------------------------------------------------
    # AI parsing

    def _run_ai_parser(
        self,
        submission: "DeviceSpecSubmission",
        scenario: Optional[ScenarioContext],
        intent_summary: str,
    ) -> Dict[str, Any]:
        narrative = submission.narrative.strip()
        if not narrative:
            return {}

        payload = {
            "player_id": submission.player_id,
            "scenario_id": submission.scenario_id or (scenario.scenario_id if scenario else "default"),
            "narrative": narrative,
            "given": {
                "world_constraints": sanitize_lines(submission.world_constraints),
                "logic_outline": sanitize_lines(submission.logic_outline),
                "success_criteria": sanitize_lines(submission.success_criteria),
                "risk_register": sanitize_lines(submission.risk_register),
                "resource_ledger": sanitize_lines(submission.resource_ledger),
            },
            "defaults": {
                "scenario_constraints": (scenario.contextual_constraints if scenario else []),
                "scenario_success_markers": (scenario.success_markers if scenario else []),
                "scenario_risks": (scenario.emerging_risks if scenario else []),
            },
            "intent_hint": intent_summary,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 Ideal City 裁决前置处理器。"
                    "将玩家口语叙述整理成结构化 JSON。"
                    "必须返回如下键：intent_summary, world_constraints, logic_outline,"
                    " success_criteria, risk_register, resource_ledger, is_draft。"
                    "所有取值均为字符串、布尔值或字符串列表，不得生成空对象。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]

        try:
            ai_result = call_deepseek(
                {"task": "ideal_city_spec_normalizer"},
                messages,
                temperature=0.15,
                response_format={"type": "json_object"},
                connect_timeout=SPEC_AI_CONNECT_TIMEOUT,
                read_timeout=SPEC_AI_READ_TIMEOUT,
            )
        except Exception:
            return {}

        parsed = ai_result.get("parsed")
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                parsed = None
        if parsed is None:
            try:
                parsed = json.loads(ai_result.get("response", "{}"))
            except (TypeError, json.JSONDecodeError):
                return {}

        if not isinstance(parsed, dict):
            return {}

        cleaned: Dict[str, Any] = {}
        for key in (
            "intent_summary",
            "world_constraints",
            "logic_outline",
            "success_criteria",
            "risk_register",
            "resource_ledger",
        ):
            value = parsed.get(key)
            if isinstance(value, str):
                cleaned[key] = value.strip()
            elif isinstance(value, list):
                cleaned[key] = sanitize_lines([str(item) for item in value])
        if "is_draft" in parsed:
            cleaned["is_draft"] = parsed.get("is_draft")
        return cleaned

    # ---------------------------------------------------------------------
    # Heuristic fallback

    def _heuristic_projection(
        self,
        narrative: str,
        scenario: Optional[ScenarioContext],
        intent_summary: str,
    ) -> Dict[str, Any]:
        sentences = self._split_sentences(narrative)
        goal_sentence = sentences[0] if sentences else intent_summary
        execution_sentence = " ".join(sentences[1:]).strip()
        if not execution_sentence and goal_sentence:
            execution_sentence = "围绕目标拆解两步执行：准备资源并落地社区验证。"

        logic_outline: List[str] = []
        if goal_sentence:
            logic_outline.append(f"目标：{goal_sentence}")
        if execution_sentence:
            logic_outline.append(f"执行：{execution_sentence}")

        world_constraints: List[str] = []
        if scenario and scenario.contextual_constraints:
            world_constraints.extend(scenario.contextual_constraints)

        success_criteria: List[str] = []
        if scenario and scenario.success_markers:
            success_criteria.extend(scenario.success_markers[:2])

        risk_register: List[str] = []
        if scenario and scenario.emerging_risks:
            risk_register.extend(scenario.emerging_risks[:2])

        is_draft = False
        lowered = narrative.lower()
        if "draft" in lowered or "草稿" in lowered:
            is_draft = True

        return {
            "world_constraints": sanitize_lines(world_constraints),
            "logic_outline": sanitize_lines(logic_outline),
            "success_criteria": sanitize_lines(success_criteria),
            "risk_register": sanitize_lines(risk_register),
            "resource_ledger": [],
            "is_draft": is_draft,
        }

    @staticmethod
    def _summarise_intent(narrative: str) -> str:
        for line in narrative.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        return narrative.strip()

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        if not text:
            return []
        parts = re.split(r"[。\.!?！？；;]\s*", text)
        return [part.strip() for part in parts if part and part.strip()]

    @staticmethod
    def _pick_nonempty(*candidates: Any) -> List[str]:
        for candidate in candidates:
            if not candidate:
                continue
            if isinstance(candidate, str):
                lines = sanitize_lines([candidate])
            elif isinstance(candidate, list):
                lines = sanitize_lines([str(item) for item in candidate])
            else:
                continue
            if lines:
                # Preserve order while removing duplicates.
                seen = []
                for line in lines:
                    if line not in seen:
                        seen.append(line)
                return seen
        return []

    def _ensure_logic_depth(self, logic_outline: List[str], narrative: str) -> List[str]:
        return logic_outline