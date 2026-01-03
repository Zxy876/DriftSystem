"""World narrator that announces execution updates across the shard."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.core.ai.deepseek_agent import call_deepseek
from .ai_settings import AI_CONNECT_TIMEOUT, AI_READ_TIMEOUT

from .adjudication_contract import AdjudicationRecord
from .build_plan import BuildPlan
from .device_spec import DeviceSpec
from .scenario_repository import ScenarioContext


_WORLD_NARRATOR_PROMPT = """
你是理想之城广播站的叙事员，要把最新的裁决与建造计划广播给城内的居民。
输出 JSON：
{
  "title": "广播标题",
  "spoken": ["第一句", "第二句"],
  "call_to_action": "简短号召"
}
语气：沉稳、纪实，强调人与城的关系；每句不超过 80 字。
如果信息不足，请在 call_to_action 提醒玩家回到档案馆补交材料。
""".strip()


class WorldNarration(BaseModel):
    title: str
    spoken: List[str]
    call_to_action: str


@dataclass
class NarrationContext:
    spec: DeviceSpec
    ruling: AdjudicationRecord
    scenario: ScenarioContext
    build_plan: Optional[BuildPlan]


class WorldNarratorAgent:
    """Generate structured narration for broadcasts."""

    def __init__(self) -> None:
        self._cache: Dict[str, WorldNarration] = {}

    def narrate(self, ctx: NarrationContext) -> WorldNarration:
        cache_key = self._cache_key(ctx)
        if cache_key in self._cache:
            return self._cache[cache_key]

        payload = self._build_payload(ctx)
        messages = [
            {"role": "system", "content": _WORLD_NARRATOR_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        response = call_deepseek(
            payload,
            messages,
            temperature=0.4,
            connect_timeout=AI_CONNECT_TIMEOUT,
            read_timeout=AI_READ_TIMEOUT,
        )
        narration = self._parse_response(response)
        if narration is None:
            narration = self._fallback(ctx)
        self._cache[cache_key] = narration
        return narration

    def _parse_response(self, response: object) -> Optional[WorldNarration]:
        if not isinstance(response, dict):
            return None
        parsed = response.get("parsed")
        if not isinstance(parsed, dict):
            return None
        title = parsed.get("title")
        spoken = parsed.get("spoken")
        call_to_action = parsed.get("call_to_action")
        if not title or not spoken:
            return None
        if not isinstance(spoken, list):
            return None
        spoken_lines = [str(line) for line in spoken if line]
        if not spoken_lines:
            return None
        return WorldNarration(
            title=str(title),
            spoken=spoken_lines,
            call_to_action=str(call_to_action) if call_to_action else "返回档案馆确认补交资料。",
        )

    def _fallback(self, ctx: NarrationContext) -> WorldNarration:
        title = f"理想之城广播：{ctx.spec.intent_summary[:18]}"
        spoken = [
            f"档案馆确认 {ctx.spec.author_ref} 的提案正在准备执行。",
            f"裁决结果：{ctx.ruling.verdict.value}，理由：{ctx.ruling.reasoning[0] if ctx.ruling.reasoning else '详见档案' }。",
        ]
        if ctx.build_plan and ctx.build_plan.steps:
            step = ctx.build_plan.steps[0]
            spoken.append(f"第一步：{step.title}——{step.description[:40]}。")
        call_to_action = "参与社区讨论，协助标注风险与资源。"
        return WorldNarration(title=title, spoken=spoken, call_to_action=call_to_action)

    def _build_payload(self, ctx: NarrationContext) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "spec": {
                "author": ctx.spec.author_ref,
                "intent": ctx.spec.intent_summary,
            },
            "ruling": {
                "verdict": ctx.ruling.verdict.value,
                "reasoning": ctx.ruling.reasoning,
            },
            "scenario": {
                "id": ctx.scenario.scenario_id,
                "title": ctx.scenario.title,
            },
        }
        if ctx.build_plan:
            payload["build_plan"] = {
                "summary": ctx.build_plan.summary,
                "steps": [step.title for step in ctx.build_plan.steps],
            }
        return payload

    @staticmethod
    def _cache_key(ctx: NarrationContext) -> str:
        blob = json.dumps(
            {
                "spec_id": ctx.spec.spec_id,
                "verdict": ctx.ruling.verdict.value,
                "plan_id": str(ctx.build_plan.plan_id) if ctx.build_plan else None,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode()).hexdigest()
