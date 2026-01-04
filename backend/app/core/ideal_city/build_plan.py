"""Shared data models for build plans generated after adjudication."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BuildPlanStatus(str, Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    completed = "completed"
    blocked = "blocked"


class BuildStep(BaseModel):
    step_id: str
    title: str
    description: str
    target_region: Optional[str] = None
    required_mod: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)


class BuildPlan(BaseModel):
    plan_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str
    status: BuildPlanStatus = BuildPlanStatus.pending
    steps: List[BuildStep] = Field(default_factory=list)
    resource_ledger: Dict[str, str] = Field(default_factory=dict)
    risk_notes: List[str] = Field(default_factory=list)
    mod_hooks: List[str] = Field(default_factory=list)
    origin_scenario: Optional[str] = None

    def to_storage_dict(self) -> Dict[str, object]:
        data = self.model_dump(mode="json")
        data["created_at"] = self.created_at.isoformat()
        data["plan_id"] = str(self.plan_id)
        return data

    @classmethod
    def from_llm_response(cls, response: Dict[str, object], default_summary: str) -> Optional["BuildPlan"]:
        if not isinstance(response, dict):
            return None
        summary = response.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = default_summary
        steps_payload = response.get("steps")
        steps: List[BuildStep] = []
        if isinstance(steps_payload, list):
            for idx, raw in enumerate(steps_payload, start=1):
                if not isinstance(raw, dict):
                    continue
                title = raw.get("title")
                description = raw.get("description")
                if not title or not description:
                    continue
                step = BuildStep(
                    step_id=raw.get("step_id") or f"step-{idx}",
                    title=str(title),
                    description=str(description),
                    target_region=str(raw.get("target_region")) if raw.get("target_region") else None,
                    required_mod=str(raw.get("required_mod")) if raw.get("required_mod") else None,
                    dependencies=[str(dep) for dep in raw.get("dependencies", []) if dep],
                )
                steps.append(step)
        resource_ledger = {}
        raw_ledger = response.get("resource_ledger")
        if isinstance(raw_ledger, dict):
            resource_ledger = {str(k): str(v) for k, v in raw_ledger.items()}
        mod_hooks = []
        raw_hooks = response.get("mod_hooks")
        if isinstance(raw_hooks, list):
            mod_hooks = [str(entry) for entry in raw_hooks if entry]
        risk_notes = []
        raw_risks = response.get("risk_notes")
        if isinstance(raw_risks, list):
            risk_notes = [str(entry) for entry in raw_risks if entry]
        origin_scenario = response.get("origin_scenario")
        if origin_scenario is not None:
            origin_scenario = str(origin_scenario)
        return cls(
            summary=summary.strip(),
            steps=steps,
            resource_ledger=resource_ledger,
            mod_hooks=mod_hooks,
            risk_notes=risk_notes,
            origin_scenario=origin_scenario,
        )


# Keywords captured from typical in-game phrasing so the deterministic
# fallback can still resolve mod hooks when LLM calls fail. Keep the list
# small and explicit to avoid false positives.
_MOD_KEYWORDS: Dict[str, List[str]] = {
    "gm4:balloon_animals": [
        "\u6c14\u7403\u52a8\u7269",
        "\u5e86\u5178\u6c14\u7403",
        "balloon animal",
        "gm4_balloon_animals",
        "gm4:balloon_animals",
    ],
    "gm4:better_armour_stands": [
        "\u76d4\u7532\u67b6",
        "armour stand",
        "better armour stand",
        "gm4_better_armour_stands",
        "gm4:better_armour_stands",
    ],
    "gm4:lively_lily_pads": [
        "\u7761\u83b2",
        "lily pad",
        "lively lily",
        "gm4_lively_lily_pads",
        "gm4:lively_lily_pads",
    ],
    "gm4:tunnel_bores": [
        "\u6398\u8fdb\u673a",
        "tunnel bore",
        "\u96a7\u9053\u673a\u5668",
        "gm4_tunnel_bores",
        "gm4:tunnel_bores",
    ],
    "gm4:tower_structures": [
        "\u5854\u697c",
        "tower structure",
        "gm4_tower_structures",
        "gm4:tower_structures",
    ],
    "gm4:boots_of_ostara": [
        "ostara",
        "\u6625\u4e4b\u9774",
        "gm4_boots_of_ostara",
        "gm4:boots_of_ostara",
    ],
    "gm4:lib_custom_crafters": [
        "\u81ea\u5b9a\u4e49\u5408\u6210\u53f0",
        "custom crafter",
        "gm4_custom_crafters",
        "gm4:lib_custom_crafters",
    ],
    "gm4:lib_trades": [
        "\u6751\u6c11\u4ea4\u6613\u5e93",
        "trade library",
        "gm4_trades",
        "gm4:lib_trades",
    ],
    "gm4:lib_trees": [
        "\u6811\u6728\u5e93",
        "tree library",
        "gm4_trees",
        "gm4:lib_trees",
    ],
}

_COMMAND_TO_MOD: Dict[str, str] = {
    "gm4_balloon_animals:init": "gm4:balloon_animals",
    "gm4_better_armour_stands:init": "gm4:better_armour_stands",
    "gm4_lively_lily_pads:init": "gm4:lively_lily_pads",
    "gm4_tunnel_bores:init": "gm4:tunnel_bores",
    "gm4_tower_structures:init": "gm4:tower_structures",
    "gm4_boots_of_ostara:init": "gm4:boots_of_ostara",
    "gm4_custom_crafters:load": "gm4:lib_custom_crafters",
    "gm4_trades:load": "gm4:lib_trades",
    "gm4_trees:load": "gm4:lib_trees",
}


def _derive_mod_hooks(spec_intent: str, logic_outline: List[str]) -> List[str]:
    haystack = "\n".join(filter(None, [spec_intent, *logic_outline])).lower()
    found: Set[str] = set()
    for command, mod_id in _COMMAND_TO_MOD.items():
        if command in haystack:
            found.add(mod_id)
    for mod_id, keywords in _MOD_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in haystack:
                found.add(mod_id)
                break
    return sorted(found)


def build_plan_from_spec(spec_intent: str, logic_outline: List[str], scenario_id: Optional[str]) -> BuildPlan:
    """Fallback deterministic plan derived from logic outline."""

    summary = spec_intent or "执行经裁决批准的方案"
    steps: List[BuildStep] = []
    for index, entry in enumerate(logic_outline, start=1):
        cleaned = entry.strip()
        if not cleaned:
            continue
        steps.append(
            BuildStep(
                step_id=f"fallback-{index}",
                title=f"阶段 {index}",
                description=cleaned,
            )
        )
    if not steps:
        steps.append(
            BuildStep(
                step_id="fallback-1",
                title="完成裁决要求",
                description="按照裁决说明执行任务，并在完成后回报档案馆。",
            )
        )
    mod_hooks = _derive_mod_hooks(spec_intent or "", logic_outline or [])
    return BuildPlan(
        summary=summary.strip(),
        steps=steps,
        origin_scenario=scenario_id,
        mod_hooks=mod_hooks,
    )
