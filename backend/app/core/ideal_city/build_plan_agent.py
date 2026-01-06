"""LLM-backed build plan generator translating specs into execution plans."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.core.ai.deepseek_agent import call_deepseek
from .ai_settings import AI_CONNECT_TIMEOUT, AI_READ_TIMEOUT

from .adjudication_contract import AdjudicationRecord, VerdictEnum
from .build_plan import BuildPlan, BuildStep, augment_mod_hooks, build_plan_from_spec
from .device_spec import DeviceSpec
from .scenario_repository import ScenarioContext
from .story_state import StoryState


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
- 任何字段都不得为 null 或空数组；若无有效内容，请直接省略该字段。
- steps[].dependencies 必须是包含有效前置步骤 ID 的数组，若无依赖请省略 dependencies 字段。
- target_region 与 required_mod 可缺省。
- 参考世界观约束与裁决条件，确保步骤可执行并与世界观一致。
""".strip()


@dataclass
class BuildPlanContext:
    spec: DeviceSpec
    ruling: AdjudicationRecord
    scenario: ScenarioContext
    story_state: Optional[StoryState] = None


class BuildPlanAgent:
    """Generate structured build plans using LLM with robust fallback."""

    def __init__(self) -> None:
        self._cache: Dict[str, BuildPlan] = {}

    def generate(self, ctx: BuildPlanContext) -> Optional[BuildPlan]:
        if ctx.ruling.verdict not in {VerdictEnum.ACCEPT, VerdictEnum.PARTIAL}:
            return None
        ready_state = ctx.story_state if ctx.story_state and ctx.story_state.ready_for_build else None
        spec_for_plan = ctx.spec
        if ready_state:
            spec_for_plan = ctx.spec.model_copy(
                update={
                    "intent_summary": ready_state.goals[-1]
                    if ready_state.goals
                    else ctx.spec.intent_summary,
                    "logic_outline": ready_state.logic_outline or ctx.spec.logic_outline,
                    "resource_ledger": ready_state.resources or ctx.spec.resource_ledger,
                    "success_criteria": ready_state.success_criteria or ctx.spec.success_criteria,
                    "risk_register": ready_state.risk_register or ctx.spec.risk_register,
                }
            )
        cache_key = self._cache_key(spec_for_plan, ctx.ruling)
        if cache_key in self._cache:
            return self._cache[cache_key]
        payload = self._build_payload(ctx, spec_for_plan, ready_state)
        llm_response = self._call_llm(payload)
        plan: Optional[BuildPlan] = None
        if llm_response is not None:
            plan = BuildPlan.from_llm_response(llm_response, default_summary=spec_for_plan.intent_summary)
        if plan is None or self._is_generic(plan):
            plan = self._deterministic_from_state(ctx, spec_for_plan, ready_state)
        if plan is None:
            plan = build_plan_from_spec(
                spec_for_plan.intent_summary,
                spec_for_plan.logic_outline,
                ctx.scenario.scenario_id,
            )
        extra_clues: List[str] = []
        if spec_for_plan.intent_summary:
            extra_clues.append(spec_for_plan.intent_summary)
        extra_clues.extend(spec_for_plan.logic_outline or [])
        if ready_state:
            extra_clues.extend(ready_state.notes)
            extra_clues.extend(ready_state.community_requirements)
            extra_clues.extend(ready_state.success_criteria)
        augment_mod_hooks(plan, extra_clues)
        if ready_state and plan.player_pose is None and ready_state.player_pose is not None:
            plan.player_pose = ready_state.player_pose
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

    def _build_payload(
        self,
        ctx: BuildPlanContext,
        spec: DeviceSpec,
        story_state: Optional[StoryState],
    ) -> Dict[str, object]:
        scenario = ctx.scenario
        ruling = ctx.ruling
        payload: Dict[str, object] = {
            "device_spec": {
                "intent": spec.intent_summary,
                "logic_outline": spec.logic_outline,
                "constraints": spec.world_constraints,
                "resources": spec.resource_ledger,
                "success_criteria": spec.success_criteria,
                "risk_register": spec.risk_register,
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
        if story_state:
            payload["story_state"] = {
                "goals": story_state.goals,
                "logic_outline": story_state.logic_outline,
                "resources": story_state.resources,
                "community_requirements": story_state.community_requirements,
                "success_criteria": story_state.success_criteria,
                "risk_register": story_state.risk_register,
                "location_hint": story_state.location_hint,
                "player_pose": story_state.player_pose.model_dump(mode="json") if story_state.player_pose else None,
                "risk_notes": story_state.risk_notes,
                "ready_for_build": story_state.ready_for_build,
                "build_capability": story_state.build_capability,
                "blocking": story_state.blocking,
            }
        return payload

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

    @staticmethod
    def _is_generic(plan: Optional[BuildPlan]) -> bool:
        if plan is None:
            return True
        if not plan.steps:
            return True
        return all(step.step_id.startswith("fallback-") for step in plan.steps)

    def _deterministic_from_state(
        self,
        ctx: BuildPlanContext,
        spec: DeviceSpec,
        state: Optional[StoryState],
    ) -> Optional[BuildPlan]:
        if state is None:
            return None
        summary = state.goals[-1] if state.goals else spec.intent_summary or "理想之城建造计划"
        steps: List[BuildStep] = []
        dependencies: List[str] = []

        if state.resources:
            desc = self._format_resources(state.resources)
            step = BuildStep(
                step_id="phase-resources",
                title="协调资源",
                description=desc,
                target_region=spec.scenario_id,
                required_mod=None,
                dependencies=[],
            )
            steps.append(step)
            dependencies = [step.step_id]

        if state.community_requirements:
            desc = "确认展台满足居民期待：" + "；".join(state.community_requirements)
            step = BuildStep(
                step_id="phase-community",
                title="社区共创",
                description=desc,
                target_region=spec.scenario_id,
                required_mod=None,
                dependencies=dependencies.copy(),
            )
            steps.append(step)
            dependencies = [step.step_id]

        if state.success_criteria:
            desc = "达成标准：" + "；".join(state.success_criteria)
            step = BuildStep(
                step_id="phase-success",
                title="验收标准",
                description=desc,
                target_region=spec.scenario_id,
                required_mod=None,
                dependencies=dependencies.copy(),
            )
            steps.append(step)
            dependencies = [step.step_id]

        location_text = state.location_hint or spec.intent_summary
        build_desc = f"在 {location_text} 落地 GM4 气球展台并点亮周边。"
        step = BuildStep(
            step_id="phase-execution",
            title="执行建造",
            description=build_desc,
            target_region=location_text,
            required_mod="gm4:balloon_animals" if "balloon" in summary.lower() or "气球" in summary else None,
            dependencies=dependencies.copy(),
        )
        steps.append(step)

        resource_ledger = self._resource_ledger_from_list(state.resources)
        plan = BuildPlan(
            summary=summary,
            steps=steps,
            resource_ledger=resource_ledger,
            risk_notes=state.risk_register or state.risk_notes or spec.risk_register,
            mod_hooks=[],
            origin_scenario=ctx.scenario.scenario_id,
            player_pose=state.player_pose,
        )
        if "gm4" in summary.lower() or "气球" in summary or "气球" in "".join(state.notes):
            plan.mod_hooks = ["gm4:balloon_animals"]
        return plan

    @staticmethod
    def _format_resources(resources: List[str]) -> str:
        if not resources:
            return ""
        return "；".join(resources)

    @staticmethod
    def _resource_ledger_from_list(resources: List[str]) -> Dict[str, str]:
        ledger: Dict[str, str] = {}
        for idx, item in enumerate(resources, start=1):
            text = item.strip()
            if not text:
                continue
            key, value = BuildPlanAgent._split_resource_entry(text, idx)
            ledger[key] = value
        return ledger

    @staticmethod
    def _split_resource_entry(text: str, idx: int) -> Tuple[str, str]:
        for delimiter in ("：", ":", "-", "--"):
            if delimiter in text:
                left, right = text.split(delimiter, 1)
                return left.strip() or f"资源{idx}", right.strip() or "待确认"
        return f"资源{idx}", text
