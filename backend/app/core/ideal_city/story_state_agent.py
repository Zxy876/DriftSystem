"""Narrative agent that infers structured story state slots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re

from app.core.ai.deepseek_agent import call_deepseek

from .ai_settings import AI_CONNECT_TIMEOUT, AI_READ_TIMEOUT
from .device_spec import DeviceSpec
from .scenario_repository import ScenarioContext
from .story_state import StoryState, StoryStatePatch
from .story_state_phase import determine_phase


_PLACEHOLDER_PATTERN = re.compile(r"\b(?:todo|tbd|待补|待定|占位|placeholder|无|暂无)\b", re.IGNORECASE)


_STORY_STATE_SYSTEM_PROMPT = """
你是理想之城 adjudication pipeline 的 StoryStateAgent，负责把玩家叙述转成完整的审查档案。
仅返回 JSON，字段必须与下列样例完全一致：
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
审查规则：
- 核心字段 {logic_outline, world_constraints, resources, success_criteria, risk_register} 不能留空且禁止占位词（TODO、待补、TBD 等）。
- 每条 resources 必须使用 "资源项 - 责任人" 格式。
- risk_register 必须使用 "风险: 描述 / 缓解" 格式。
- 依据 motivation_score：
    * ≥70：必须补齐所有核心字段，最多允许一个 blocking 理由并解释原因。
    * 40-69：至少补齐 logic_outline、world_constraints，对其余缺口写入 follow_up_questions。
    * <40：不要编造资源/风险，聚焦提问，blocking 列出缺失项。
- coverage 中的布尔值需准确反映是否满足上述格式与数量要求。
- blocking 列出阻塞建造的条目，使用简洁中文短语。
- motivation_score 代表建造意愿；建造裁决 = 意愿 + 逻辑表达补全。意愿足够时要主动补全核心字段。
- 任何字段不得返回 null 或空数组；如果无内容，直接省略对应字段并在 follow_up_questions 或 risk_notes 中说明缺口。
- 不得使用占位词或“暂无/待补”之类含义的语句。
""".strip()


_STAGE_PROMPTS: Dict[str, str] = {
    "vision": "聚焦愿景与执行脉络，确认 logic_outline、world_constraints、success_criteria 是否覆盖关键信息。",
    "resources": "盘点资源与风险，确保 resources 与 risk_register 列表符合格式，缺失就提出追问。",
    "location": "锁定位置、风险收尾，若仍缺核心字段要明确追问，提醒玩家同步 /cityphone pose。",
    "wrap": "回顾覆盖情况，若 blocking 为空则给出简短肯定，仍有缺口则说明补齐步骤。",
}

_HISTORY_LIMIT = 8


@dataclass
class StoryStateAgentContext:
    narrative: str
    spec: DeviceSpec
    scenario: ScenarioContext
    existing_state: StoryState


class StoryStateAgent:
    """LLM-first agent with deterministic fallback."""

    def infer(self, ctx: StoryStateAgentContext) -> StoryStatePatch:
        parsed = self._call_llm(ctx)
        if parsed is None:
            return self._fallback(ctx)
        return parsed

    def _call_llm(self, ctx: StoryStateAgentContext) -> Optional[StoryStatePatch]:
        stage = determine_phase(ctx.existing_state)
        payload = {
            "narrative": ctx.narrative,
            "spec": {
                "intent": ctx.spec.intent_summary,
                "logic_outline": ctx.spec.logic_outline,
                "resources": ctx.spec.resource_ledger,
                "success": ctx.spec.success_criteria,
            },
            "scenario": {
                "id": ctx.scenario.scenario_id,
                "title": ctx.scenario.title,
                "problem": ctx.scenario.problem_statement,
                "constraints": ctx.scenario.contextual_constraints,
            },
            "existing_state": ctx.existing_state.model_dump(mode="json"),
            "phase": stage,
            "history": self._conversation_memory(ctx.existing_state),
        }
        stage_prompt = _STAGE_PROMPTS.get(stage, "")
        system_prompt = _STORY_STATE_SYSTEM_PROMPT
        if stage_prompt:
            system_prompt = f"{system_prompt}\n\n当前阶段：{stage_prompt}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        response = call_deepseek(
            payload,
            messages,
            temperature=0.2,
            connect_timeout=AI_CONNECT_TIMEOUT,
            read_timeout=AI_READ_TIMEOUT,
        )
        if not isinstance(response, dict):
            return None
        raw = response.get("parsed")
        if not isinstance(raw, dict):
            return None
        return self._normalise(raw)

    def _normalise(self, raw: dict) -> StoryStatePatch:
        def _list(key: str, formatter: Optional[str] = None) -> Optional[List[str]]:
            values = raw.get(key)
            if not isinstance(values, list):
                return None
            cleaned: List[str] = []
            for item in values:
                text = str(item).strip()
                if not text:
                    continue
                if _is_placeholder(text):
                    continue
                if formatter == "resource":
                    formatted = _normalise_resource(text)
                    if not formatted:
                        continue
                    text = formatted
                elif formatter == "risk":
                    formatted = _normalise_risk(text)
                    if not formatted:
                        continue
                    text = formatted
                cleaned.append(text)
            return cleaned or None

        location_hint = raw.get("location_hint")
        if isinstance(location_hint, str):
            location_hint = location_hint.strip() or None
        else:
            location_hint = None

        coverage = raw.get("coverage") if isinstance(raw.get("coverage"), dict) else {}
        normalised_coverage: Dict[str, bool] = {}
        for key, value in coverage.items():
            normalised_coverage[str(key)] = bool(value)

        blocking = _list("blocking")

        return StoryStatePatch(
            goals=_list("goals"),
            logic_outline=_list("logic_outline"),
            resources=_list("resources", formatter="resource"),
            community_requirements=_list("community_requirements"),
            world_constraints=_list("world_constraints"),
            success_criteria=_list("success_criteria"),
            risk_register=_list("risk_register", formatter="risk"),
            risk_notes=_list("risk_notes"),
            location_hint=location_hint,
            follow_up_questions=_list("follow_up_questions"),
            blocking=blocking,
            coverage=normalised_coverage or None,
            motivation_score=_as_int(raw.get("motivation_score")),
        )

    def _fallback(self, ctx: StoryStateAgentContext) -> StoryStatePatch:
        stage = determine_phase(ctx.existing_state)
        text = ctx.narrative.strip()
        inferred_resources = _ensure_resource_fallback(ctx, _infer_resources(text))
        community = _infer_community_expectations(text)
        inferred_success = _fallback_success(ctx, community)
        inferred_risk = _fallback_risk(ctx, text)

        scenario = ctx.scenario
        minimal_autofill = len(text) <= 20

        if minimal_autofill:
            focus = (ctx.spec.intent_summary or text or (scenario.title if scenario else "城市建造")).strip() or "城市建造"
            partner = (scenario.stakeholders[0] if scenario and scenario.stakeholders else "社区志愿者").strip() or "社区志愿者"

            def _normalised(items: List[str], *, formatter: Optional[str] = None) -> List[str]:
                cleaned: List[str] = []
                seen: set[str] = set()
                for item in items:
                    text_item = str(item).strip()
                    if not text_item or _is_placeholder(text_item):
                        continue
                    if formatter == "resource":
                        text_item = _normalise_resource(text_item) or ""
                    elif formatter == "risk":
                        text_item = _normalise_risk(text_item) or ""
                    if not text_item:
                        continue
                    if text_item in seen:
                        continue
                    seen.add(text_item)
                    cleaned.append(text_item)
                return cleaned

            logic_outline = _normalised(list(ctx.spec.logic_outline or []) + list(ctx.existing_state.logic_outline or []))
            if len(logic_outline) < 2:
                default_logic = [
                    f"与{partner}共创{focus}蓝图",
                    "布置现场并进行试运营",
                ]
                logic_outline = _normalised([*logic_outline, *default_logic])

            world_constraints = _normalised(list(ctx.spec.world_constraints or []) + list(ctx.existing_state.world_constraints or []))
            if not world_constraints:
                default_constraints: List[str] = []
                if scenario and scenario.contextual_constraints:
                    default_constraints.extend(scenario.contextual_constraints[:2])
                default_constraints.extend(["遵守噪音管制", "控制夜间能耗"])
                world_constraints = _normalised(default_constraints)

            resource_candidates = list(ctx.spec.resource_ledger or []) + list(ctx.existing_state.resources or []) + inferred_resources
            default_resources = [
                f"{focus}材料 - {partner}",
                f"灯光设备 - {partner}",
            ]
            resources = _normalised(resource_candidates if resource_candidates else default_resources, formatter="resource")
            if not resources:
                resources = _normalised(default_resources, formatter="resource")

            success_candidates = list(ctx.spec.success_criteria or []) + list(ctx.existing_state.success_criteria or []) + inferred_success
            if not success_candidates and scenario and scenario.success_markers:
                success_candidates.extend(scenario.success_markers[:2])
            default_success = ["居民愿意持续参与至少一周", "现场运行无安全事故"]
            success_criteria = _normalised(success_candidates if success_candidates else default_success)
            if not success_criteria:
                success_criteria = _normalised(default_success)

            risk_candidates = list(ctx.spec.risk_register or []) + list(ctx.existing_state.risk_register or []) + inferred_risk
            if not risk_candidates and scenario and scenario.emerging_risks:
                for risk in scenario.emerging_risks[:2]:
                    risk_candidates.append(f"风险: {risk} / 安排轮值维护")
            default_risks = ["风险: 夜间安全不足 / 安排志愿者巡查"]
            risk_register = _normalised(risk_candidates if risk_candidates else default_risks, formatter="risk")
            if not risk_register:
                risk_register = _normalised(default_risks, formatter="risk")

            location_hint = _infer_location_hint(text)
            if not location_hint and ctx.existing_state.location_hint:
                location_hint = ctx.existing_state.location_hint
            if not location_hint and scenario and scenario.title:
                location_hint = f"{scenario.title}附近"
            if not location_hint:
                location_hint = "社区主街露天平台"

            motivation_boost = max(ctx.existing_state.motivation_score, 80)

            coverage = {
                "logic_outline": _has_entries(logic_outline, min_count=2),
                "world_constraints": _has_entries(world_constraints, min_count=1),
                "resource_ledger": _has_entries(resources, min_count=1, formatter="resource"),
                "success_criteria": _has_entries(success_criteria, min_count=1),
                "risk_register": _has_entries(risk_register, min_count=1, formatter="risk"),
            }

            follow_up: List[str] = []
            if stage == "location" and ctx.existing_state.player_pose is None:
                follow_up.append("有空的话把现场坐标贴给我（/taskdebug pose 就可以），这样工坊更好落位。")

            return StoryStatePatch(
                logic_outline=logic_outline or None,
                resources=resources or None,
                community_requirements=community or None,
                world_constraints=world_constraints or None,
                success_criteria=success_criteria or None,
                risk_register=risk_register or None,
                follow_up_questions=follow_up or None,
                location_hint=location_hint,
                blocking=None,
                coverage=coverage,
                motivation_score=motivation_boost,
            )

        location_hint = _infer_location_hint(text)

        logic_sources = list(ctx.spec.logic_outline or []) + list(ctx.existing_state.logic_outline or [])
        world_sources = list(ctx.spec.world_constraints or []) + list(ctx.existing_state.world_constraints or [])
        resource_sources = list(ctx.spec.resource_ledger or []) + list(ctx.existing_state.resources or []) + inferred_resources
        success_sources = list(ctx.spec.success_criteria or []) + list(ctx.existing_state.success_criteria or []) + inferred_success
        risk_sources = list(ctx.spec.risk_register or []) + list(ctx.existing_state.risk_register or []) + inferred_risk

        logic_covered = _has_entries(logic_sources, min_count=2)
        constraints_covered = _has_entries(world_sources, min_count=1)
        resources_covered = _has_entries(resource_sources, min_count=1, formatter="resource")
        success_covered = _has_entries(success_sources, min_count=1)
        risk_covered = _has_entries(risk_sources, min_count=1, formatter="risk")

        missing_logic = not logic_covered
        missing_constraints = not constraints_covered
        missing_resources = not resources_covered
        missing_success = not success_covered
        missing_risk = not risk_covered

        follow_up: List[str] = []
        if stage == "location" and ctx.existing_state.player_pose is None:
            follow_up.append("有空的话把现场坐标贴给我（/taskdebug pose 就可以），这样工坊更好落位。")
        blocking_entries = []

        def _dedupe(items: List[str]) -> List[str]:
            seen: set[str] = set()
            ordered: List[str] = []
            for item in items:
                key = item.strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                ordered.append(key)
            return ordered

        follow_up = _dedupe(follow_up)
        blocking_entries = _dedupe(blocking_entries)

        return StoryStatePatch(
            resources=inferred_resources or None,
            community_requirements=community or None,
            success_criteria=inferred_success or None,
            risk_register=inferred_risk or None,
            follow_up_questions=follow_up or None,
            location_hint=location_hint,
            blocking=blocking_entries or None,
            coverage={
                "logic_outline": logic_covered,
                "world_constraints": constraints_covered,
                "resource_ledger": resources_covered,
                "success_criteria": success_covered,
                "risk_register": risk_covered,
            },
        )

    def _conversation_memory(self, state: StoryState) -> Dict[str, object]:
        notes = [line for line in state.notes if line and line.strip()]
        trimmed = notes[-_HISTORY_LIMIT:]
        memory = {
            "recent_notes": trimmed,
            "listed_resources": state.resources or [],
            "community_expectations": state.community_requirements or [],
            "last_pose": state.player_pose.model_dump(mode="json") if state.player_pose else None,
            "asked_questions": state.open_questions[-3:],
        }
        return memory


def _infer_resources(text: str) -> List[str]:
    if not text:
        return []
    entries: List[str] = []
    pattern = re.compile(r"(?P<provider>[\u4e00-\u9fffA-Za-z0-9]{1,12})(?:正在|愿意|会|将)?提供(?P<item>[^，。；；\n]+)")
    for match in pattern.finditer(text):
        provider = match.group("provider").strip()
        item = match.group("item").strip()
        if not provider or not item:
            continue
        entries.append(f"{item}由{provider}提供")
    # 如果文本中提到“筹备”“准备”，也尝试收集
    if not entries:
        prep_pattern = re.compile(r"(?P<actor>[\u4e00-\u9fffA-Za-z0-9]{1,12})(?:负责|筹备|准备)(?P<item>[^，。；；\n]+)")
        for match in prep_pattern.finditer(text):
            actor = match.group("actor").strip()
            item = match.group("item").strip()
            if not actor or not item:
                continue
            entries.append(f"{item}由{actor}筹备")
    return entries


def _normalise_resource(text: str) -> Optional[str]:
    candidate = text.strip()
    if not candidate:
        return None
    if "-" in candidate:
        parts = [part.strip() for part in candidate.split("-", 1)]
        if len(parts) == 2 and all(parts):
            return f"{parts[0]} - {parts[1]}"
    if "由" in candidate and "" != candidate:
        match = re.search(r"(?P<item>.+?)由(?P<owner>[^提供赠借]+)", candidate)
        if match:
            item = match.group("item").strip()
            owner = match.group("owner").strip()
            if item and owner:
                return f"{item} - {owner}"
    split_pattern = re.compile(r"[:：]\s*")
    if split_pattern.search(candidate):
        parts = split_pattern.split(candidate, maxsplit=1)
        if len(parts) == 2 and all(part.strip() for part in parts):
            return f"{parts[0].strip()} - {parts[1].strip()}"
    return candidate if " - " in candidate else None


def _normalise_risk(text: str) -> Optional[str]:
    candidate = text.strip()
    if not candidate:
        return None
    match = re.match(r"风险[:：]\s*(.+)", candidate)
    if match:
        rest = match.group(1).strip()
        parts = [part.strip() for part in rest.split("/", 1)]
        if len(parts) == 2 and all(parts):
            return f"风险: {parts[0]} / {parts[1]}"
        return None
    if "/" in candidate:
        parts = [seg.strip() for seg in candidate.split("/", 1)]
        if len(parts) == 2 and all(parts):
            return f"风险: {parts[0]} / {parts[1]}"
    segments = re.split(r"[:：]", candidate, maxsplit=1)
    if len(segments) == 2:
        topic = segments[0].strip()
        rest = segments[1].strip()
        if not topic or not rest:
            return None
        return _normalise_risk(f"风险: {topic} / {rest}")
    return None


def _is_placeholder(text: str) -> bool:
    return bool(_PLACEHOLDER_PATTERN.search(text))


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return max(0, min(200, int(value)))
    except (TypeError, ValueError):
        return None


def _ensure_resource_fallback(ctx: StoryStateAgentContext, inferred: List[str]) -> List[str]:
    if inferred:
        normalised = [entry for entry in (_normalise_resource(item) or "" for item in inferred) if entry]
        if normalised:
            return normalised
    return []


def _fallback_success(ctx: StoryStateAgentContext, community: List[str]) -> List[str]:
    if ctx.spec.success_criteria or ctx.existing_state.success_criteria:
        return []
    return []


def _fallback_risk(ctx: StoryStateAgentContext, narrative: str) -> List[str]:
    if ctx.spec.risk_register or ctx.existing_state.risk_register:
        return []
    entries: List[str] = []
    pattern = re.compile(r"风险[:：]\s*(?P<risk>[^/]+)/(?:\s*)(?P<mitigation>[^，。；\n]+)")
    for match in pattern.finditer(narrative):
        risk = match.group("risk").strip()
        mitigation = match.group("mitigation").strip()
        if risk and mitigation:
            formatted = _normalise_risk(f"风险: {risk} / {mitigation}")
            if formatted:
                entries.append(formatted)
    return entries


def _has_entries(entries: List[str], *, min_count: int, formatter: Optional[str] = None) -> bool:
    cleaned: List[str] = []
    for item in entries:
        text = str(item).strip()
        if not text:
            continue
        if _is_placeholder(text):
            continue
        if formatter == "resource" and " - " not in text:
            formatted = _normalise_resource(text)
            if not formatted:
                continue
            text = formatted
        if formatter == "risk":
            formatted = _normalise_risk(text)
            if not formatted:
                continue
            text = formatted
        cleaned.append(text)
        if len(cleaned) >= min_count:
            return True
    return False


def _infer_community_expectations(text: str) -> List[str]:
    if not text:
        return []
    segments = [seg.strip() for seg in re.split(r"[。！？!?\n]", text) if seg.strip()]
    results: List[str] = []
    for seg in segments:
        if "居民" in seg and any(token in seg for token in ("希望", "盼", "能", "让", "期待")):
            results.append(seg)
    return results


def _infer_location_hint(text: str) -> Optional[str]:
    if not text:
        return None
    pattern = re.compile(r"在(?P<place>[\u4e00-\u9fffA-Za-z0-9\s]{1,24}?)(?:旁|附近|内|里|周边|入口|附近)")
    match = pattern.search(text)
    if match:
        return f"{match.group('place').strip()}附近"
    # catch “放在X”
    pattern = re.compile(r"放在(?P<place>[\u4e00-\u9fffA-Za-z0-9\s]{1,24})")
    match = pattern.search(text)
    if match:
        return f"{match.group('place').strip()}"
    return None
