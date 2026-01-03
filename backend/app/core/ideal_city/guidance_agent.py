"""LLM-assisted guidance generator for Ideal City adjudications."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from app.core.ai.deepseek_agent import call_deepseek
from .ai_settings import AI_CONNECT_TIMEOUT, AI_READ_TIMEOUT
from .adjudication_contract import AdjudicationRecord, VerdictEnum
from .device_spec import DeviceSpec
from .scenario_repository import ScenarioContext
from .worldview import WorldviewContext


_GUIDANCE_SYSTEM_PROMPT = """
你是《创造之城》档案馆的辅导档案员，负责在裁决后给出下一步建议。
必须返回 JSON，格式严格为：
{
  "guidance": [
    {
      "kind": "constraint|logic|risk|context|exploration",
      "text": "...具体建议...",
      "priority": 1
    }
  ]
}
约束：
- 优先参考输入提供的世界约束、逻辑步骤、风险登记与裁决理由。
- 每条建议不超过 120 字，语气温和坚定，符合档案馆的记录口吻。
- 如果信息不足以给出具体建议，用 kind "context" 提醒玩家补充信息。
- priority 越小表示越紧急，范围 1-3。
""".strip()


class GuidanceItem(BaseModel):
    kind: str = Field(default="context")
    text: str
    priority: int = Field(default=2)


@dataclass
class GuidanceContext:
    spec: DeviceSpec
    ruling: AdjudicationRecord
    scenario: ScenarioContext
    worldview: WorldviewContext


class GuidanceAgent:
    """Generate post-ruling guidance with LLM fallback heuristics."""

    def __init__(self) -> None:
        self._cache: Dict[str, List[GuidanceItem]] = {}

    def generate(self, ctx: GuidanceContext) -> List[GuidanceItem]:
        cache_key = self._cache_key(ctx.spec, ctx.ruling)
        if cache_key in self._cache:
            return self._cache[cache_key]

        payload = self._build_payload(ctx)
        parsed_items = self._call_llm(payload)
        if not parsed_items:
            parsed_items = self._fallback_guidance(ctx)

        self._cache[cache_key] = parsed_items
        return parsed_items

    def _call_llm(self, payload: Dict[str, object]) -> List[GuidanceItem]:
        messages = [
            {"role": "system", "content": _GUIDANCE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]
        response = call_deepseek(
            payload,
            messages,
            temperature=0.35,
            connect_timeout=AI_CONNECT_TIMEOUT,
            read_timeout=AI_READ_TIMEOUT,
        )
        parsed = response.get("parsed") if isinstance(response, dict) else None
        items: List[GuidanceItem] = []
        if isinstance(parsed, dict):
            raw_guidance = parsed.get("guidance")
            if isinstance(raw_guidance, list):
                for entry in raw_guidance:
                    item = self._normalise_entry(entry)
                    if item:
                        items.append(item)
        return items

    def _normalise_entry(self, entry: object) -> Optional[GuidanceItem]:
        if not isinstance(entry, dict):
            return None
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        kind = entry.get("kind")
        priority = entry.get("priority")
        try:
            parsed_priority = int(priority) if priority is not None else 2
        except (TypeError, ValueError):
            parsed_priority = 2
        parsed_priority = max(1, min(parsed_priority, 5))
        kind_str = str(kind).strip() if isinstance(kind, str) and kind.strip() else "context"
        return GuidanceItem(kind=kind_str, text=text.strip(), priority=parsed_priority)

    def _fallback_guidance(self, ctx: GuidanceContext) -> List[GuidanceItem]:
        guidance: List[GuidanceItem] = []
        spec = ctx.spec
        ruling = ctx.ruling

        if not spec.world_constraints:
            guidance.append(
                GuidanceItem(
                    kind="constraint",
                    priority=1,
                    text="补充至少一条已确认的世界约束，让工坊知道你遵守哪些边界。",
                )
            )
        if len(spec.logic_outline) < 2:
            guidance.append(
                GuidanceItem(
                    kind="logic",
                    priority=1,
                    text="用两步以上说明执行顺序，让社区可以监督每个阶段的进展。",
                )
            )
        if ruling.verdict != VerdictEnum.ACCEPT and not spec.risk_register:
            guidance.append(
                GuidanceItem(
                    kind="risk",
                    priority=2,
                    text="写下可能的风险或故障点，档案馆才能安排巡夜与补救。",
                )
            )
        if not guidance:
            guidance.append(
                GuidanceItem(
                    kind="context",
                    priority=2,
                    text="档案员建议：回顾熄灯区档案，确认你的方案如何回应居民最急迫的困境。",
                )
            )
        return guidance

    def _build_payload(self, ctx: GuidanceContext) -> Dict[str, object]:
        spec = ctx.spec
        scenario = ctx.scenario
        worldview = ctx.worldview
        ruling = ctx.ruling

        return {
            "worldview": {
                "spirit": worldview.spirit_core,
                "principles": worldview.design_principles,
                "forbidden": worldview.forbidden_patterns,
            },
            "scenario": {
                "id": scenario.scenario_id,
                "title": scenario.title,
                "problem": scenario.problem_statement,
                "constraints": scenario.contextual_constraints,
            },
            "device_spec": {
                "intent": spec.intent_summary,
                "world_constraints": spec.world_constraints,
                "logic_outline": spec.logic_outline,
                "risk_register": spec.risk_register,
                "success_criteria": spec.success_criteria,
            },
            "ruling": {
                "verdict": ruling.verdict.value,
                "reasoning": ruling.reasoning,
                "conditions": ruling.conditions,
            },
        }

    @staticmethod
    def _cache_key(spec: DeviceSpec, ruling: AdjudicationRecord) -> str:
        payload = {
            "spec": {
                "intent": spec.intent_summary,
                "constraints": spec.world_constraints,
                "logic": spec.logic_outline,
                "risk": spec.risk_register,
            },
            "ruling": {
                "verdict": ruling.verdict.value,
                "reasoning": ruling.reasoning,
                "conditions": ruling.conditions,
            },
        }
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()


def render_guidance_text(items: Iterable[GuidanceItem]) -> List[str]:
    """Convert guidance entries to human-readable strings for notices."""

    lines: List[str] = []
    for item in items:
        prefix = {
            "constraint": "补充约束",
            "logic": "完善步骤",
            "risk": "登记风险",
            "context": "补充语境",
            "exploration": "扩展探索",
        }.get(item.kind, "建议")
        lines.append(f"{prefix}：{item.text}")
    return lines
