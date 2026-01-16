"""Story state co-ordination between narrative guidance and build pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
import re

from .device_spec import DeviceSpec, sanitize_lines
from .guidance_agent import GuidanceItem
from .story_state import StoryState, StoryStatePatch
from .story_state_repository import StoryStateRepository
from .build_plan import PlayerPose
from .scenario_repository import ScenarioContext
from .story_state_phase import determine_phase

if False:  # type checking helper
    from .story_state_agent import StoryStateAgent, StoryStateAgentContext


@dataclass
class StoryStateOutcome:
    state: StoryState
    enriched_spec: DeviceSpec
    guidance: List[GuidanceItem]
    missing_slots: Dict[str, str]

    @property
    def ready_for_build(self) -> bool:
        return self.state.ready_for_build


class StoryStateManager:
    """High-level orchestrator for accumulating and validating story state."""

    def __init__(self, repository: StoryStateRepository, agent: Optional["StoryStateAgent"] = None) -> None:
        self._repository = repository
        self._agent = agent
        self._placeholder_pattern = re.compile(r"\b(?:todo|tbd|待补|待定|占位|placeholder|暂无|无)\b", re.IGNORECASE)
        self._core_field_messages = {
            "logic_outline": "需补：执行逻辑，请至少写 1 步（可用模板按钮补齐）。",
            "world_constraints": "需补：世界约束，请列出关键限制（模板按钮可快速添加）。",
            "resource_ledger": "需补：资源清单，可描述“物料 - 负责人”（模板按钮可补齐）。",
            "success_criteria": "需补：成功标准，写出验收方式（模板按钮可补齐）。",
            "risk_register": "需补：风险登记，写出风险/缓解（模板按钮可补齐）。",
        }
        self._template_presets: Dict[str, Dict[str, object]] = {
            "logic_quick_start": {
                "adds": {
                    "logic_outline": [
                        "目标：在熄灯区入口搭建安全的气球展台，引导访客。",
                        "执行：现场布置与社区验证两步完成部署。",
                    ]
                },
                "message_applied": "已添加执行逻辑示例。",
                "message_existing": "执行逻辑已包含该模板内容。",
            },
            "constraint_night_quiet": {
                "adds": {
                    "world_constraints": [
                        "夜间施工需控制噪音，遵守熄灯区安静时段。",
                    ]
                },
                "message_applied": "已补充世界约束模板。",
                "message_existing": "世界约束已包含该条目。",
            },
            "resource_basic": {
                "adds": {
                    "resources": [
                        "气球展台基础材料 - 档案官提供",
                    ]
                },
                "message_applied": "已加入基础资源清单。",
                "message_existing": "资源清单已包含该模板。",
            },
            "risk_safety": {
                "adds": {
                    "risk_register": [
                        "风险: 夜间噪音扰民 / 设定静音演示时段",
                    ]
                },
                "message_applied": "已加入风险登记模板。",
                "message_existing": "风险登记已包含该条目。",
            },
            "success_night_showcase": {
                "adds": {
                    "success_criteria": [
                        "夜间入口亮度足够，居民对气球展台反馈满意。",
                    ]
                },
                "message_applied": "已补充成功标准模板。",
                "message_existing": "成功标准已包含该条目。",
            },
        }

    @dataclass
    class EvaluationResult:
        coverage: Dict[str, bool]
        blocking: List[str]
        guidance: Dict[str, str]
        motivation_score: int
        logic_score: int
        build_capability: int

    @dataclass
    class TemplateApplication:
        state: StoryState
        applied: bool
        message: str
        reason: Optional[str] = None

    def process(
        self,
        *,
        player_id: str,
        scenario_id: str,
        scenario: ScenarioContext,
        spec: DeviceSpec,
        narrative: str,
        player_pose: Optional[PlayerPose],
    ) -> StoryStateOutcome:
        existing = self._repository.load(player_id, scenario_id)
        if existing is None:
            existing = StoryState(player_id=player_id, scenario_id=scenario_id)

        patch: Optional[StoryStatePatch] = None
        if self._agent is not None:
            from .story_state_agent import StoryStateAgentContext

            patch = self._agent.infer(
                StoryStateAgentContext(
                    narrative=narrative,
                    spec=spec,
                    scenario=scenario,
                    existing_state=existing,
                )
            )

        merged_state = self._merge(existing, spec, narrative, player_pose, patch)
        evaluation = self._evaluate(existing, merged_state, narrative, player_pose, patch)

        missing_slots: Dict[str, str] = dict(evaluation.guidance)
        if patch and patch.follow_up_questions:
            for idx, question in enumerate(patch.follow_up_questions, start=1):
                if not question:
                    continue
                text = question.strip()
                if not text:
                    continue
                missing_slots.setdefault(f"follow_up_{idx}", text)

        open_questions = self._deduplicate([
            *missing_slots.values(),
            *evaluation.blocking,
        ])

        ready_flag = evaluation.build_capability >= 85 and not evaluation.blocking

        merged_state = merged_state.model_copy(
            update={
                "ready_for_build": ready_flag,
                "open_questions": open_questions,
                "blocking": evaluation.blocking,
                "coverage": evaluation.coverage,
                "motivation_score": evaluation.motivation_score,
                "logic_score": evaluation.logic_score,
                "build_capability": evaluation.build_capability,
                "version": merged_state.version + 1,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._repository.save(merged_state)

        enriched_spec = self._apply_state_to_spec(spec, merged_state)
        guidance = self._guidance_from_missing(missing_slots)
        return StoryStateOutcome(
            state=merged_state,
            enriched_spec=enriched_spec,
            guidance=guidance,
            missing_slots=missing_slots,
        )

    def _merge(
        self,
        state: StoryState,
        spec: DeviceSpec,
        narrative: str,
        player_pose: Optional[PlayerPose],
        patch: Optional[StoryStatePatch],
    ) -> StoryState:
        extra_goals = patch.goals if patch and patch.goals else []
        extra_logic = patch.logic_outline if patch and patch.logic_outline else []
        extra_resources = patch.resources if patch and patch.resources else []
        extra_community = patch.community_requirements if patch and patch.community_requirements else []
        extra_constraints = patch.world_constraints if patch and patch.world_constraints else []
        extra_success = patch.success_criteria if patch and patch.success_criteria else []
        extra_risks = patch.risk_notes if patch and patch.risk_notes else []
        extra_register = patch.risk_register if patch and patch.risk_register else []
        extra_notes = patch.notes if patch and patch.notes else []

        goals = _merge_unique(state.goals, [spec.intent_summary, *extra_goals])
        logic_outline = _merge_unique(state.logic_outline, [*spec.logic_outline, *extra_logic])
        world_constraints = _merge_unique(state.world_constraints, [*spec.world_constraints, *extra_constraints])
        resources = _merge_unique(state.resources, [*spec.resource_ledger, *extra_resources])
        community_requirements = _merge_unique(state.community_requirements, [*extra_community])
        success_criteria = _merge_unique(state.success_criteria, [*spec.success_criteria, *extra_success])
        risk_register = _merge_unique(state.risk_register, [*spec.risk_register, *extra_register])
        risk_notes = _merge_unique(state.risk_notes, [*extra_risks])
        notes = _merge_unique(state.notes, [*sanitize_lines(narrative.splitlines()), *extra_notes])
        location_hint = state.location_hint
        pose = state.player_pose
        if player_pose is not None:
            pose = player_pose
            location_hint = location_hint or _pose_to_hint(player_pose)
        elif patch and patch.player_pose is not None:
            pose = patch.player_pose
            location_hint = location_hint or _pose_to_hint(patch.player_pose)
        if patch and patch.location_hint:
            location_hint = patch.location_hint
        resources = self._normalise_collection(resources, formatter="resource")
        risk_register = self._normalise_collection(risk_register, formatter="risk")
        success_criteria = self._normalise_collection(success_criteria)
        if not resources:
            resources = ["气球展台基础材料 - 档案官提供"]
        if not risk_register:
            risk_register = ["风险: 气球设备维护不足 / 定期巡检安排"]
        return state.model_copy(
            update={
                "goals": goals,
                "logic_outline": logic_outline,
                "world_constraints": world_constraints,
                "resources": resources,
                "community_requirements": community_requirements,
                "success_criteria": success_criteria,
                "risk_notes": risk_notes,
                "risk_register": risk_register,
                "notes": notes,
                "player_pose": pose,
                "location_hint": location_hint,
            }
        )

    def _evaluate(
        self,
        previous: StoryState,
        current: StoryState,
        narrative: str,
        player_pose: Optional[PlayerPose],
        patch: Optional[StoryStatePatch],
    ) -> "StoryStateManager.EvaluationResult":
        coverage = self._compute_coverage(current)
        logic_score = self._logic_score_from_coverage(coverage)
        motivation_score = self._compute_motivation(previous, current, narrative, player_pose, patch)
        build_capability = max(0, min(200, motivation_score + logic_score))

        blocking_inputs: List[str] = []
        if patch and patch.blocking:
            blocking_inputs.extend(patch.blocking)
        for field, fulfilled in coverage.items():
            if not fulfilled:
                message = self._core_field_messages.get(field)
                if message:
                    blocking_inputs.append(message)
        if logic_score < 50:
            blocking_inputs.append(f"逻辑评分不足 50（当前 {logic_score}）")
        blocking = self._deduplicate(blocking_inputs)

        guidance: Dict[str, str] = {}
        for field, fulfilled in coverage.items():
            if not fulfilled:
                guidance[field] = self._core_field_messages.get(field, "")
        if current.player_pose is None:
            guidance.setdefault("location", "同步一次坐标（/cityphone pose）以便定位施工点。")

        return StoryStateManager.EvaluationResult(
            coverage=coverage,
            blocking=blocking,
            guidance=guidance,
            motivation_score=motivation_score,
            logic_score=logic_score,
            build_capability=build_capability,
        )

    def _compute_coverage(self, state: StoryState) -> Dict[str, bool]:
        return {
            "logic_outline": self._has_entries(state.logic_outline, min_count=1),
            "world_constraints": self._has_entries(state.world_constraints, min_count=1),
            "resource_ledger": self._has_entries(state.resources, min_count=1),
            "success_criteria": self._has_entries(state.success_criteria, min_count=1),
            "risk_register": self._has_entries(state.risk_register, min_count=1),
        }

    def _has_entries(self, entries: List[str], *, min_count: int) -> bool:
        if not entries:
            return False
        cleaned: List[str] = []
        for item in entries:
            text = self._clean_entry(item)
            if not text:
                continue
            cleaned.append(text)
        return len(cleaned) >= min_count

    def _clean_entry(self, value: str) -> Optional[str]:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        if self._placeholder_pattern.search(text):
            return None
        return text

    def _normalise_collection(self, entries: List[str], formatter: Optional[str] = None) -> List[str]:
        ordered: List[str] = []
        seen: set[str] = set()
        for item in entries:
            text = self._clean_entry(item)
            if not text:
                continue
            if formatter == "resource":
                text = self._normalise_resource_entry(text)
            elif formatter == "risk":
                text = self._normalise_risk_entry(text)
            if not text:
                continue
            if text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    def _normalise_resource_entry(self, value: str) -> Optional[str]:
        if " - " in value:
            return value
        if "-" in value:
            parts = [part.strip() for part in value.split("-", 1)]
            if len(parts) == 2 and all(parts):
                return f"{parts[0]} - {parts[1]}"
        match = re.search(r"(?P<item>.+?)由(?P<owner>[^提供赠借]+)", value)
        if match:
            item = match.group("item").strip()
            owner = match.group("owner").strip()
            if item and owner:
                return f"{item} - {owner}"
        colon_split = re.split(r"[:：]", value, maxsplit=1)
        if len(colon_split) == 2:
            left = colon_split[0].strip()
            right = colon_split[1].strip()
            if left and right:
                return f"{left} - {right}"
        return f"{value} - 待确认"

    def _normalise_risk_entry(self, value: str) -> Optional[str]:
        match = re.match(r"风险[:：]\s*(.+)", value)
        if match:
            rest = match.group(1).strip()
            parts = [part.strip() for part in rest.split("/", 1)]
            if len(parts) == 2 and all(parts):
                return f"风险: {parts[0]} / {parts[1]}"
            return f"风险: {rest} / 待补充"
        if "/" in value:
            parts = [part.strip() for part in value.split("/", 1)]
            if len(parts) == 2 and all(parts):
                return f"风险: {parts[0]} / {parts[1]}"
            if parts[0]:
                return f"风险: {parts[0]} / 待补充"
        colon_split = re.split(r"[:：]", value, maxsplit=1)
        if len(colon_split) == 2:
            left = colon_split[0].strip()
            right = colon_split[1].strip()
            if left and right:
                return self._normalise_risk_entry(f"风险: {left} / {right}")
        return f"风险: {value} / 待补充"

    def _logic_score_from_coverage(self, coverage: Dict[str, bool]) -> int:
        score = 0
        for field in ("logic_outline", "world_constraints", "resource_ledger", "success_criteria", "risk_register"):
            if coverage.get(field):
                score += 18
        return max(60, score)

    def _compute_motivation(
        self,
        previous: StoryState,
        current: StoryState,
        narrative: str,
        player_pose: Optional[PlayerPose],
        patch: Optional[StoryStatePatch],
    ) -> int:
        text = (narrative or "").strip()
        length_score = min(60, len(text) // 5)

        update_score = 0
        if len(current.resources) > len(previous.resources):
            delta = len(current.resources) - len(previous.resources)
            update_score += min(20, 10 + delta * 6)
        if player_pose is not None and previous.player_pose is None:
            update_score += 18
        elif player_pose is not None:
            update_score += 8
        if len(current.success_criteria) > len(previous.success_criteria):
            update_score += 6
        update_score = min(update_score, 35)

        prev_coverage = self._compute_coverage(previous)
        curr_coverage = self._compute_coverage(current)
        responsiveness = 0
        for field, covered in curr_coverage.items():
            if covered and not prev_coverage.get(field, False):
                responsiveness += 5
        responsiveness = min(responsiveness, 15)

        computed = min(100, length_score + update_score + responsiveness)
        if patch and patch.motivation_score is not None:
            computed = max(computed, patch.motivation_score)
        computed = max(computed, previous.motivation_score)
        return computed

    def _deduplicate(self, entries: List[str]) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for item in entries:
            if not item:
                continue
            text = str(item).strip()
            if not text:
                continue
            if text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def phase_for(self, state: StoryState) -> str:
        return determine_phase(state)

    def _apply_state_to_spec(self, spec: DeviceSpec, state: StoryState) -> DeviceSpec:
        update = {
            "world_constraints": state.world_constraints or spec.world_constraints,
            "logic_outline": state.logic_outline or spec.logic_outline,
            "resource_ledger": state.resources or spec.resource_ledger,
            "success_criteria": state.success_criteria or spec.success_criteria,
            "risk_register": state.risk_register or spec.risk_register,
        }
        return spec.model_copy(update=update)

    def _guidance_from_missing(self, missing: Dict[str, str]) -> List[GuidanceItem]:
        if not missing:
            return []
        guidance: List[GuidanceItem] = []
        seen_text: set[str] = set()
        for slot, prompt in missing.items():
            if slot == "resource_ledger" or slot == "resources":
                if prompt and prompt not in seen_text:
                    guidance.append(GuidanceItem(kind="context", priority=1, text=prompt))
                    seen_text.add(prompt)
            elif slot == "logic_outline":
                if prompt and prompt not in seen_text:
                    guidance.append(GuidanceItem(kind="logic", priority=1, text=prompt))
                    seen_text.add(prompt)
            elif slot == "world_constraints":
                if prompt and prompt not in seen_text:
                    guidance.append(GuidanceItem(kind="constraint", priority=1, text=prompt))
                    seen_text.add(prompt)
            elif slot == "success_criteria":
                if prompt and prompt not in seen_text:
                    guidance.append(GuidanceItem(kind="exploration", priority=2, text=prompt))
                    seen_text.add(prompt)
            elif slot == "risk_register":
                if prompt and prompt not in seen_text:
                    guidance.append(GuidanceItem(kind="constraint", priority=1, text=prompt))
                    seen_text.add(prompt)
            elif slot == "community":
                if prompt and prompt not in seen_text:
                    guidance.append(GuidanceItem(kind="exploration", priority=2, text=prompt))
                    seen_text.add(prompt)
            elif slot == "location":
                if prompt and prompt not in seen_text:
                    guidance.append(GuidanceItem(kind="constraint", priority=1, text=prompt))
                    seen_text.add(prompt)
            else:
                if prompt and prompt not in seen_text:
                    guidance.append(GuidanceItem(kind="context", priority=2, text=prompt))
                    seen_text.add(prompt)
        return guidance

    def apply_template(
        self,
        *,
        player_id: str,
        scenario_id: str,
        template_key: str,
    ) -> "StoryStateManager.TemplateApplication":
        state = self._repository.load(player_id, scenario_id)
        if state is None:
            state = StoryState(player_id=player_id, scenario_id=scenario_id)
        return StoryStateManager.TemplateApplication(
            state=state,
            applied=False,
            message="模板功能已封存，仅供查阅。",
            reason="template_archived",
        )

    def sync_execution_feedback(
        self,
        *,
        player_id: str,
        scenario_id: str,
        plan_id: Optional[str],
        status: Optional[str],
        command_count: int,
        missing_mods: Optional[List[str]] = None,
        summary: Optional[str] = None,
        log_path: Optional[str] = None,
    ) -> StoryState:
        state = self._repository.load(player_id, scenario_id)
        if state is None:
            state = StoryState(player_id=player_id, scenario_id=scenario_id)
        if not plan_id:
            return state

        status_value = (status or "unknown").strip() or "unknown"
        tail = plan_id if len(plan_id) <= 12 else plan_id[-6:]
        headline = summary.strip() if isinstance(summary, str) else "建造计划"
        base = f"[计划 {tail}] {headline}"
        mods_text = ""
        if status_value == "completed" and command_count > 0:
            detail = f"建造完成，派发 {command_count} 条指令。"
        elif status_value == "completed":
            detail = "建造完成，未检测到派发指令。"
        elif status_value == "blocked" and missing_mods:
            mods_text = ", ".join(sorted({mod for mod in missing_mods if mod}))
            detail = f"建造受阻，缺少模组：{mods_text}。"
        elif status_value == "blocked":
            detail = "建造受阻，请查看执行日志。"
        else:
            detail = f"建造状态更新：{status_value}。"
        if log_path:
            detail = f"{detail} (日志: {log_path})"
        note = f"{base} · {detail}"

        already_synced = (
            state.last_plan_id == plan_id
            and state.last_plan_status == status_value
            and note in state.notes
        )
        if already_synced:
            return state

        prefix = f"{base} ·"
        notes = [entry for entry in state.notes if not entry.startswith(prefix)]
        if note not in notes:
            notes.append(note)
        if len(notes) > 12:
            notes = notes[-12:]
        notes = self._deduplicate(notes)

        update: Dict[str, object] = {
            "notes": notes,
            "last_plan_id": plan_id,
            "last_plan_status": status_value,
            "last_plan_synced_at": datetime.now(timezone.utc),
            "version": state.version + 1,
            "updated_at": datetime.now(timezone.utc),
        }

        block_reason: Optional[str] = None
        if status_value == "blocked":
            if mods_text:
                block_reason = f"缺少模组：{mods_text}"
            else:
                block_reason = "建造执行受阻，请检查日志。"

        if status_value == "completed":
            update["ready_for_build"] = False
            update["open_questions"] = []
            update["blocking"] = []
        else:
            update["ready_for_build"] = False
            if block_reason:
                existing = list(state.blocking)
                existing.append(block_reason)
                update["blocking"] = self._deduplicate(existing)

        updated = state.model_copy(update=update)
        self._repository.save(updated)
        return updated

    def apply_pose_update(
        self,
        *,
        player_id: str,
        scenario_id: str,
        pose: PlayerPose,
        location_hint: Optional[str] = None,
    ) -> StoryState:
        state = self._repository.load(player_id, scenario_id)
        if state is None:
            state = StoryState(player_id=player_id, scenario_id=scenario_id)
        hint = location_hint or state.location_hint or _pose_to_hint(pose)
        updated_base = state.model_copy(update={"player_pose": pose, "location_hint": hint})
        evaluation = self._evaluate(state, updated_base, "", pose, None)
        missing_slots = dict(evaluation.guidance)
        open_questions = self._deduplicate([*missing_slots.values(), *evaluation.blocking])
        ready_flag = evaluation.build_capability >= 85 and not evaluation.blocking
        updated = updated_base.model_copy(
            update={
                "ready_for_build": ready_flag,
                "open_questions": open_questions,
                "blocking": evaluation.blocking,
                "coverage": evaluation.coverage,
                "motivation_score": evaluation.motivation_score,
                "logic_score": evaluation.logic_score,
                "build_capability": evaluation.build_capability,
                "version": updated_base.version + 1,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._repository.save(updated)
        return updated


def _merge_unique(existing: List[str], additions: List[str]) -> List[str]:
    seen = {item.strip(): item.strip() for item in existing if item and item.strip()}
    ordered: List[str] = [value for value in seen.values()]
    for entry in additions:
        if not entry:
            continue
        candidate = entry.strip()
        if not candidate:
            continue
        if candidate not in seen:
            seen[candidate] = candidate
            ordered.append(candidate)
    return ordered


def _pose_to_hint(pose: PlayerPose) -> str:
    return f"{pose.world} @ {pose.x:.2f}, {pose.y:.2f}, {pose.z:.2f}"
