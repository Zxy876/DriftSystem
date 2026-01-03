"""LLM-backed build plan generator translating specs into execution plans."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.core.ai.deepseek_agent import call_deepseek
from .ai_settings import AI_CONNECT_TIMEOUT, AI_READ_TIMEOUT

from .adjudication_contract import AdjudicationRecord, VerdictEnum
from .build_plan import BuildPlan, build_plan_from_spec
from .device_spec import DeviceSpec
from .scenario_repository import ScenarioContext


_BUILD_PLAN_SYSTEM_PROMPT = """
你是理想之城改造工坊的执行排程员，负责把审理通过的装置规划转成可执行的建造计划。
务必返回 JSON，格式：
{
  "summary": "一句概括",
  "steps": [
    {
      "step_id": "string",
      "title": "string",
      "description": "string",
      "target_region": "string?",
      "required_mod": "string?",
      "dependencies": ["step_id"]
    }
  ],
  "resource_ledger": {
     "resource_name": "来源或提供方"
  },
  "risk_notes": ["..."],
  "mod_hooks": ["mod.namespace"],
  "origin_scenario": "scenario-id"
}
约束：
- 只根据提供的数据安排，缺失信息时标注在 risk_notes。
- target_region 与 required_mod 可缺省。
- 参考世界观约束与裁决条件，确保步骤可执行。
""".strip()


@dataclass
class BuildPlanContext:
    spec: DeviceSpec
    ruling: AdjudicationRecord
    scenario: ScenarioContext


class BuildPlanAgent:
    """Generate structured build plans using LLM with robust fallback."""

    def __init__(self) -> None:
        self._cache: Dict[str, BuildPlan] = {}

    def generate(self, ctx: BuildPlanContext) -> Optional[BuildPlan]:
        if ctx.ruling.verdict not in {VerdictEnum.ACCEPT, VerdictEnum.PARTIAL}:
            return None
        cache_key = self._cache_key(ctx.spec, ctx.ruling)
        if cache_key in self._cache:
            return self._cache[cache_key]
        payload = self._build_payload(ctx)
        llm_response = self._call_llm(payload)
        plan: Optional[BuildPlan] = None
        if llm_response is not None:
            plan = BuildPlan.from_llm_response(llm_response, default_summary=ctx.spec.intent_summary)
        if plan is None:
            plan = build_plan_from_spec(
                ctx.spec.intent_summary,
                ctx.spec.logic_outline,
                ctx.scenario.scenario_id,
            )
        self._cache[cache_key] = plan
        return plan

    def _call_llm(self, payload: Dict[str, object]) -> Optional[Dict[str, object]]:
        messages = [
            {"role": "system", "content": _BUILD_PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        response = call_deepseek(
            payload,
            messages,
            temperature=0.25,
            connect_timeout=AI_CONNECT_TIMEOUT,
            read_timeout=AI_READ_TIMEOUT,
        )
        if not isinstance(response, dict):
            return None
        parsed = response.get("parsed")
        if isinstance(parsed, dict):
            return parsed
        return None

    def _build_payload(self, ctx: BuildPlanContext) -> Dict[str, object]:
        spec = ctx.spec
        scenario = ctx.scenario
        ruling = ctx.ruling
        return {
            "device_spec": {
                "intent": spec.intent_summary,
                "logic_outline": spec.logic_outline,
                "constraints": spec.world_constraints,
                "resources": spec.resource_ledger,
            },
            "scenario": {
                "id": scenario.scenario_id,
                "title": scenario.title,
                "problem": scenario.problem_statement,
            },
            "ruling": {
                "verdict": ruling.verdict.value,
                "conditions": ruling.conditions,
                "reasoning": ruling.reasoning,
            },
        }

    @staticmethod
    def _cache_key(spec: DeviceSpec, ruling: AdjudicationRecord) -> str:
        payload = {
            "intent": spec.intent_summary,
            "logic": spec.logic_outline,
            "constraints": spec.world_constraints,
            "ruling": ruling.model_dump(mode="json"),
        }
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()
