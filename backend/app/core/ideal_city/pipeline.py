"""Ideal City minimal submission → adjudication → execution pipeline.

This module wires the semantic DeviceSpec objects to world-sovereign adjudication
and execution notices while strictly upholding guardrails:
- No direct world patches or plugin callbacks.
- No algorithmic scoring engines or task fallbacks.
- All state changes occur in backend-owned storage under backend/data/ideal_city.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field

from .adjudication_contract import (
    AdjudicationRecord,
    VerdictEnum,
    freeze_for_history as freeze_ruling,
)
from .device_spec import (
    DeviceSpec,
    DeviceSpecEnvelope,
    freeze_for_history as freeze_spec,
    sanitize_lines,
)
from .build_plan import BuildPlan
from .build_plan_agent import BuildPlanAgent, BuildPlanContext
from .build_scheduler import BuildScheduler, BuildSchedulerConfig
from .execution_boundary import (
    BroadcastSnapshot,
    BuildPlanSnapshot,
    ExecutionNotice,
    build_notice,
)
from .intent_recognizer import IntentKind, detect_intent
from .spec_normalizer import SpecNormalizer
from .guidance_agent import GuidanceAgent, GuidanceContext, GuidanceItem, render_guidance_text
from .scenario_repository import ScenarioContext, ScenarioRepository
from .worldview import WorldviewContext, load_worldview
from .world_narrator import NarrationContext, WorldNarration, WorldNarratorAgent
from .adjudication_explainer import AdjudicationExplainer
from app.core.mods import ModManager


if TYPE_CHECKING:
    from .spec_normalizer import NormalizedSpec


class DeviceSpecSubmission(BaseModel):
    """Payload accepted from presentation layers."""

    player_id: str
    narrative: str
    scenario_id: Optional[str] = None
    is_draft: bool = False
    world_constraints: Optional[List[str]] = None
    logic_outline: Optional[List[str]] = None
    success_criteria: Optional[List[str]] = None
    risk_register: Optional[List[str]] = None
    resource_ledger: Optional[List[str]] = None

    def to_spec(
        self,
        normalizer: Optional[SpecNormalizer] = None,
        scenario: Optional[ScenarioContext] = None,
    ) -> DeviceSpec:
        """Convert submission into a DeviceSpec after structured normalisation."""

        narrative_stripped = self.narrative.strip()
        narrative_lines = [line.strip() for line in self.narrative.splitlines() if line.strip()]

        normalized: Optional["NormalizedSpec"] = None
        if normalizer is not None:
            normalized = normalizer.normalize(self, scenario)

        intent_summary = (normalized.intent_summary if normalized else "").strip()
        if not intent_summary:
            intent_summary = narrative_lines[0] if narrative_lines else narrative_stripped

        scenario_id = (self.scenario_id or (scenario.scenario_id if scenario else "default"))

        world_constraints = sanitize_lines((normalized.world_constraints if normalized else None) or self.world_constraints)
        logic_outline_source = None
        if normalized is not None:
            logic_outline_source = normalized.logic_outline
        elif self.logic_outline:
            logic_outline_source = self.logic_outline
        else:
            logic_outline_source = narrative_lines[1:3]
        logic_outline = sanitize_lines(logic_outline_source)

        resource_ledger = sanitize_lines((normalized.resource_ledger if normalized else None) or self.resource_ledger)
        success_criteria = sanitize_lines((normalized.success_criteria if normalized else None) or self.success_criteria)
        risk_register = sanitize_lines((normalized.risk_register if normalized else None) or self.risk_register)

        is_draft = normalized.is_draft if normalized is not None else self.is_draft

        return DeviceSpec(
            author_ref=self.player_id,
            intent_summary=intent_summary or "",
            scenario_id=scenario_id,
            is_draft=is_draft,
            raw_narrative=self.narrative,
            world_constraints=world_constraints,
            logic_outline=logic_outline,
            resource_ledger=resource_ledger,
            success_criteria=success_criteria,
            risk_register=risk_register,
        )


@dataclass
class SubmissionResult:
    spec: DeviceSpec
    ruling: AdjudicationRecord
    notice: ExecutionNotice
    scenario: ScenarioContext
    guidance: List[GuidanceItem]
    build_plan: Optional[BuildPlan]
    narration: Optional[WorldNarration]


class IdealCityRepository:
    """Thread-safe append-only storage for specs and rulings."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._lock = Lock()
        self._specs_file = base_dir / "device_specs.jsonl"
        self._rulings_file = base_dir / "adjudication_rulings.jsonl"
        self._notices_file = base_dir / "execution_notices.jsonl"
        self._build_plans_file = base_dir / "build_plans.jsonl"
        self._spec_index: Dict[str, DeviceSpec] = {}
        self._ruling_index: Dict[str, AdjudicationRecord] = {}
        self._player_latest: Dict[str, Tuple[AdjudicationRecord, ExecutionNotice]] = {}
        self._plan_index: Dict[str, BuildPlan] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        if self._specs_file.exists():
            with self._specs_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    spec = DeviceSpec(**{key: value for key, value in data.items() if key not in {"snapshot_id", "frozen_at"}})
                    self._spec_index[spec.spec_id] = spec
        if self._rulings_file.exists():
            with self._rulings_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    record = AdjudicationRecord(**{key: value for key, value in data.items() if key not in {"snapshot_id", "frozen_at"}})
                    self._ruling_index[record.device_spec_id] = record
        if self._build_plans_file.exists():
            with self._build_plans_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    try:
                        plan = BuildPlan.model_validate(data)
                    except Exception:
                        continue
                    self._plan_index[str(plan.plan_id)] = plan
        if self._notices_file.exists():
            with self._notices_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    notice = ExecutionNotice(**{key: value for key, value in data.items() if key not in {"snapshot_id", "frozen_at"}})
                    self._player_latest[notice.player_ref] = (
                        self._ruling_index.get(notice.spec_id, AdjudicationRecord(
                            device_spec_id=notice.spec_id,
                            verdict=VerdictEnum.PARTIAL,
                        )),
                        notice,
                    )

    def save(
        self,
        spec: DeviceSpec,
        ruling: AdjudicationRecord,
        notice: ExecutionNotice,
        plan: Optional[BuildPlan] = None,
    ) -> None:
        """Persist artefacts atomically."""

        with self._lock:
            self._append_json(self._specs_file, freeze_spec(spec))
            self._append_json(self._rulings_file, freeze_ruling(ruling))
            self._append_json(self._notices_file, self._freeze_notice(notice))
            if plan is not None:
                self._append_json(self._build_plans_file, plan.to_storage_dict())
                self._plan_index[str(plan.plan_id)] = plan
            self._spec_index[spec.spec_id] = spec
            self._ruling_index[ruling.device_spec_id] = ruling
            self._player_latest[notice.player_ref] = (ruling, notice)

    def _append_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _freeze_notice(self, notice: ExecutionNotice) -> dict:
        payload = notice.model_dump(mode="json")
        payload["snapshot_id"] = uuid4().hex
        payload["frozen_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    def get_spec(self, spec_id: str) -> Optional[DeviceSpec]:
        return self._spec_index.get(spec_id)

    def get_ruling(self, spec_id: str) -> Optional[AdjudicationRecord]:
        return self._ruling_index.get(spec_id)

    def latest_for_player(self, player_id: str) -> Optional[Tuple[AdjudicationRecord, ExecutionNotice]]:
        return self._player_latest.get(player_id)

    def get_plan(self, plan_id: str) -> Optional[BuildPlan]:
        return self._plan_index.get(str(plan_id))


class IdealCityAdjudicator:
    """Qualitative adjudicator that folds in worldview and scenario context."""

    def __init__(self, worldview: WorldviewContext) -> None:
        self._worldview = worldview

    def evaluate(
        self,
        spec: DeviceSpec,
        scenario: ScenarioContext,
        submission_hints: Optional[Dict[str, bool]] = None,
    ) -> Tuple[AdjudicationRecord, List[str]]:
        record = self._rule_based_decision(spec, submission_hints or {})
        context_notes = self._contextual_notes(scenario)
        return record, context_notes

    def _contextual_notes(self, scenario: ScenarioContext) -> List[str]:
        notes = self._worldview.contextualise(scenario.summary())
        if scenario.contextual_constraints:
            notes.extend(f"关卡约束：{item}" for item in scenario.contextual_constraints)
        return notes

    def _rule_based_decision(self, spec: DeviceSpec, submission_hints: Dict[str, bool]) -> AdjudicationRecord:
        missing_sections: List[str] = []
        if submission_hints.get("world_constraints_missing") or not spec.world_constraints:
            missing_sections.append("世界约束")
        if submission_hints.get("logic_outline_missing") or len(spec.logic_outline) < 2:
            missing_sections.append("执行步骤")
        if submission_hints.get("risk_register_missing") or not spec.risk_register:
            missing_sections.append("风险登记")

        optional_sections: List[str] = []
        if not spec.success_criteria:
            optional_sections.append("成功指标")
        if not spec.resource_ledger:
            optional_sections.append("资源清单")

        follow_ups = self._worldview.follow_up_templates()
        reasoning: List[str] = []
        conditions: List[str] = []
        memory_hooks: List[str] = []

        if spec.is_draft:
            verdict = VerdictEnum.REVIEW_REQUIRED
            reasoning.append("提案标记为草稿，需档案馆人工复核后再推进。")
            if missing_sections:
                reasoning.append("草稿当前缺少：" + "、".join(missing_sections) + "。")
            if follow_ups:
                conditions.extend(follow_ups[:2])
            memory_hooks.append("ideal_city_review_required")
        elif missing_sections:
            verdict = VerdictEnum.REJECT
            reasoning.append("缺少必要结构：" + "、".join(missing_sections) + "。")
            reject_lines = self._worldview.rejection_templates()
            if reject_lines:
                reasoning.append(reject_lines[0])
            for idx, item in enumerate(missing_sections):
                if idx < len(follow_ups):
                    conditions.append(follow_ups[idx])
            memory_hooks.append("ideal_city_reject")
        else:
            verdict = VerdictEnum.ACCEPT
            reasoning.append("档案馆确认提案包含必要结构，可安排后续流程。")
            if optional_sections:
                reasoning.append("档案员建议补充：" + "、".join(optional_sections) + "。")
            affirm = self._worldview.affirmation_templates()
            if affirm:
                reasoning.append(affirm[0])
            memory_hooks.append("ideal_city_accept")

        return AdjudicationRecord(
            device_spec_id=spec.spec_id,
            verdict=verdict,
            reasoning=reasoning,
            conditions=conditions if verdict != VerdictEnum.ACCEPT else [],
            memory_hooks=memory_hooks,
        )


class IdealCityPipeline:
    """Public facade used by API layer."""

    def __init__(self) -> None:
        override = os.getenv("IDEAL_CITY_DATA_ROOT")
        if override:
            data_dir = Path(override)
        else:
            backend_root = Path(__file__).resolve().parents[3]
            data_dir = backend_root / "data" / "ideal_city"
        self._repository = IdealCityRepository(data_dir)
        self._worldview = load_worldview()
        self._scenario_repo = ScenarioRepository()
        self._adjudicator = IdealCityAdjudicator(self._worldview)
        self._explainer = AdjudicationExplainer()
        self._guidance_agent = GuidanceAgent()
        self._build_plan_agent = BuildPlanAgent()
        self._narrator = WorldNarratorAgent()
        self._mod_manager = ModManager()
        scheduler_root = data_dir / "build_queue"
        self._scheduler = BuildScheduler(BuildSchedulerConfig(root_dir=scheduler_root))
        self._spec_normalizer = SpecNormalizer()

    def submit(self, submission: DeviceSpecSubmission) -> SubmissionResult:
        intent_match = detect_intent(submission.narrative)
        if intent_match and intent_match.kind == IntentKind.REFRESH_MODS:
            return self._process_mod_refresh(submission)
        scenario_id = submission.scenario_id or "default"
        scenario = self._scenario_repo.load(scenario_id)
        spec = submission.to_spec(self._spec_normalizer, scenario)
        if spec.scenario_id != scenario.scenario_id:
            scenario = self._scenario_repo.load(spec.scenario_id)
        envelope = DeviceSpecEnvelope(spec=spec, submitted_by_session=submission.player_id)
        submission_hints = self._submission_hints(submission)
        # Envelope is currently audit-only; stored via freeze call for traceability.
        ruling, context_notes = self._adjudicator.evaluate(
            envelope.spec,
            scenario,
            submission_hints=submission_hints,
        )

        guidance_ctx = GuidanceContext(
            spec=envelope.spec,
            ruling=ruling,
            scenario=scenario,
            worldview=self._worldview,
        )
        guidance_items = self._guidance_agent.generate(guidance_ctx)
        guidance_lines = render_guidance_text(guidance_items)

        explanation_line = self._explainer.build_explanation(ruling.verdict, guidance_lines)
        if explanation_line and explanation_line not in ruling.reasoning:
            ruling.reasoning.append(explanation_line)

        plan_ctx = BuildPlanContext(spec=envelope.spec, ruling=ruling, scenario=scenario)
        plan = self._build_plan_agent.generate(plan_ctx)
        plan_snapshot: Optional[BuildPlanSnapshot] = None
        if plan is not None:
            if plan.mod_hooks:
                valid_mods = [hook for hook in plan.mod_hooks if self._mod_manager.has_mod(hook)]
                plan = plan.model_copy(update={"mod_hooks": valid_mods})
            plan_snapshot = BuildPlanSnapshot(
                plan_id=str(plan.plan_id),
                summary=plan.summary,
                steps=[f"{step.step_id}: {step.title}" for step in plan.steps],
                mod_hooks=plan.mod_hooks,
            )
            self._scheduler.enqueue(plan)

        narration: Optional[WorldNarration] = None
        if plan is not None or guidance_lines:
            narration_ctx = NarrationContext(
                spec=envelope.spec,
                ruling=ruling,
                scenario=scenario,
                build_plan=plan,
            )
            narration = self._narrator.narrate(narration_ctx)

        broadcast_snapshot = (
            BroadcastSnapshot(
                title=narration.title,
                spoken=narration.spoken,
                call_to_action=narration.call_to_action,
            )
            if narration
            else None
        )

        notice = build_notice(
            submission.player_id,
            spec.spec_id,
            ruling,
            context_notes,
            guidance_lines,
            plan_snapshot,
            broadcast_snapshot,
        )
        self._repository.save(spec, ruling, notice, plan)
        return SubmissionResult(
            spec=spec,
            ruling=ruling,
            notice=notice,
            scenario=scenario,
            guidance=guidance_items,
            build_plan=plan,
            narration=narration,
        )

    def _process_mod_refresh(self, submission: DeviceSpecSubmission) -> SubmissionResult:
        self._mod_manager.reload()
        scenario_id = submission.scenario_id or "default"
        scenario = self._scenario_repo.load(scenario_id)
        spec = DeviceSpec(
            author_ref=submission.player_id,
            intent_summary="系统指令：刷新模组缓存",
            scenario_id=scenario.scenario_id,
            world_constraints=[],
            logic_outline=["刷新 mods manifest 缓存"],
            resource_ledger=[],
            success_criteria=["mods manifest 与服务器同步"],
            risk_register=[],
            raw_narrative=submission.narrative,
        )
        ruling = AdjudicationRecord(
            device_spec_id=spec.spec_id,
            verdict=VerdictEnum.ACCEPT,
            reasoning=["档案馆已刷新 mods manifest 缓存。"],
            conditions=[],
            memory_hooks=["system_mod_refresh"],
        )
        guidance_items: List[GuidanceItem] = []
        narration = WorldNarration(
            title="档案广播：模组缓存更新",
            spoken=["档案馆已重新载入 mods manifest，与工坊保持同步。"],
            call_to_action="若新增模组，请放置 manifest 并再次通知档案馆。",
        )
        broadcast_snapshot = BroadcastSnapshot(
            title=narration.title,
            spoken=narration.spoken,
            call_to_action=narration.call_to_action,
        )
        notice = build_notice(
            submission.player_id,
            spec.spec_id,
            ruling,
            context_notes=["mods manifest 缓存已刷新。"],
            guidance=[],
            build_plan=None,
            broadcast=broadcast_snapshot,
        )
        self._repository.save(spec, ruling, notice, plan=None)
        return SubmissionResult(
            spec=spec,
            ruling=ruling,
            notice=notice,
            scenario=scenario,
            guidance=guidance_items,
            build_plan=None,
            narration=narration,
        )

    def fetch_spec(self, spec_id: str) -> Optional[DeviceSpec]:
        return self._repository.get_spec(spec_id)

    def fetch_ruling(self, spec_id: str) -> Optional[AdjudicationRecord]:
        return self._repository.get_ruling(spec_id)

    def latest_for_player(self, player_id: str) -> Optional[Tuple[AdjudicationRecord, ExecutionNotice]]:
        return self._repository.latest_for_player(player_id)

    def fetch_plan(self, plan_id: str) -> Optional[BuildPlan]:
        return self._repository.get_plan(plan_id)

    def fetch_plan_by_notice(self, notice: ExecutionNotice) -> Optional[dict]:
        if not notice.build_plan or not notice.build_plan.plan_id:
            return None
        plan = self._repository.get_plan(notice.build_plan.plan_id)
        return plan.model_dump() if plan else None

    def list_mods(self) -> List[dict]:
        return [record.manifest.model_dump() for record in self._mod_manager.list_mods()]

    def refresh_mods(self) -> None:
        self._mod_manager.reload()

    @staticmethod
    def _submission_hints(submission: DeviceSpecSubmission) -> Dict[str, bool]:
        world_constraints = sanitize_lines(submission.world_constraints)
        logic_outline = sanitize_lines(submission.logic_outline)
        risk_register = sanitize_lines(submission.risk_register)
        return {
            "world_constraints_missing": submission.world_constraints is not None and not world_constraints,
            "logic_outline_missing": submission.logic_outline is not None and len(logic_outline) < 2,
            "risk_register_missing": submission.risk_register is not None and not risk_register,
        }