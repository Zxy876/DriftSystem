"""Ideal City minimal submission → adjudication → execution pipeline.

This module wires the semantic DeviceSpec objects to world-sovereign adjudication
and execution notices while strictly upholding guardrails:
- No direct world patches or plugin callbacks.
- No algorithmic scoring engines or task fallbacks.
- All state changes occur in backend-owned storage under backend/data/ideal_city.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
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
from .build_plan import BuildPlan, BuildPlanStatus, PlayerPose
from .build_plan_agent import BuildPlanAgent, BuildPlanContext
from .build_scheduler import BuildScheduler, BuildSchedulerConfig
from .execution_boundary import (
    BroadcastSnapshot,
    BuildPlanSnapshot,
    PlanLocation,
    ExecutionNotice,
    build_notice,
)
from .intent_recognizer import IntentKind, detect_intent
from .spec_normalizer import SpecNormalizer
from .guidance_agent import GuidanceAgent, GuidanceContext, GuidanceItem, render_guidance_text
from .narrative_ingestion import (
    NarrativeChatEvent,
    NarrativeChatIngestor,
    NarrativeIngestionResponse,
)
from .scenario_repository import ScenarioContext, ScenarioRepository
from .worldview import WorldviewContext, load_worldview
from .world_narrator import NarrationContext, WorldNarration, WorldNarratorAgent
from .adjudication_explainer import AdjudicationExplainer
from app.core.mods import ModManager
from .story_state import StoryState
from .story_state_repository import StoryStateRepository
from .story_state_manager import StoryStateManager
from .story_state_agent import StoryStateAgent
from .story_state_phase import determine_phase
from .social_feedback import SocialFeedbackRepository, SocialAtmospherePayload


_EXECUTE_LOCATION_PATTERN = re.compile(
    r"execute\s+in\s+(?P<world>[^\s]+)\s+positioned\s+(?P<x>-?\d+(?:\.\d+)?)\s+(?P<y>-?\d+(?:\.\d+)?)\s+(?P<z>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


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
    player_pose: Optional[PlayerPose] = None

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


@dataclass
class ExecutedPlanRecord:
    plan_id: str
    summary: str
    status: str
    commands: List[str]
    mod_hooks: List[str]
    logged_at: Optional[str]
    player_pose: Optional[PlayerPose]
    location: Optional[PlanLocation]
    log_path: Path
    missing_mods: List[str]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "summary": self.summary,
            "status": self.status,
            "commands": self.commands,
            "mod_hooks": self.mod_hooks,
            "logged_at": self.logged_at,
            "player_pose": self.player_pose.model_dump(mode="json") if self.player_pose else None,
            "location": self.location.model_dump(mode="json") if self.location else None,
            "log_path": str(self.log_path),
            "missing_mods": self.missing_mods,
        }


class CityPhoneVisionPanel(BaseModel):
    goals: List[str] = Field(default_factory=list)
    logic_outline: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    coverage: Dict[str, bool] = Field(default_factory=dict)


class CityPhoneResourcesPanel(BaseModel):
    items: List[str] = Field(default_factory=list)
    pending: bool = True
    risk_register: List[str] = Field(default_factory=list)
    risk_pending: bool = True


class CityPhoneLocationPanel(BaseModel):
    location_hint: Optional[str] = None
    player_pose: Optional[PlayerPose] = None
    pending: bool = True
    location_quality: Optional[str] = None


class CityPhonePlanPanel(BaseModel):
    available: bool = False
    summary: Optional[str] = None
    steps: List[str] = Field(default_factory=list)
    mod_hooks: List[str] = Field(default_factory=list)
    plan_id: Optional[str] = None
    status: str = "pending"
    pending_reasons: List[str] = Field(default_factory=list)


class CityPhonePanels(BaseModel):
    vision: CityPhoneVisionPanel
    resources: CityPhoneResourcesPanel
    location: CityPhoneLocationPanel
    plan: CityPhonePlanPanel


class CityPhoneStatePayload(BaseModel):
    player_id: str
    scenario_id: str
    phase: str
    ready_for_build: bool
    build_capability: int = 0
    motivation_score: int = 0
    logic_score: int = 0
    blocking: List[str] = Field(default_factory=list)
    panels: CityPhonePanels


class CityPhoneAction(BaseModel):
    player_id: str
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    scenario_id: Optional[str] = None


class CityPhoneActionResult(BaseModel):
    status: str
    state: CityPhoneStatePayload
    notice: Optional[dict] = None
    build_plan: Optional[dict] = None
    guidance: Optional[List[dict]] = None
    error: Optional[str] = None
    message: Optional[str] = None


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
        self._data_dir = data_dir
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
        story_state_root = data_dir / "story_state"
        self._story_repository = StoryStateRepository(story_state_root)
        self._story_state_agent = StoryStateAgent()
        self._story_manager = StoryStateManager(self._story_repository, agent=self._story_state_agent)
        self._narrative_ingestor = NarrativeChatIngestor()
        self._social_repo = SocialFeedbackRepository(data_dir / "protocol")

    def fetch_executed_plan(self, plan_id: str) -> Optional[ExecutedPlanRecord]:
        try:
            normalized = self._normalize_plan_id(plan_id)
        except ValueError:
            return None

        executed_dir = self._scheduler.config.root_dir / "executed"
        path = executed_dir / f"{normalized}.json"
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        commands: List[str] = []
        raw_commands = payload.get("commands")
        if isinstance(raw_commands, list):
            commands = [str(entry) for entry in raw_commands if isinstance(entry, str) and entry.strip()]

        mod_hooks: List[str] = []
        raw_mods = payload.get("mod_hooks")
        if isinstance(raw_mods, list):
            mod_hooks = [str(entry) for entry in raw_mods if isinstance(entry, str) and entry.strip()]

        player_pose: Optional[PlayerPose] = None
        raw_pose = payload.get("player_pose")
        if isinstance(raw_pose, dict):
            try:
                player_pose = PlayerPose.model_validate(raw_pose)
            except Exception:
                player_pose = None

        location = self._extract_plan_location(commands, player_pose)

        notes_payload = payload.get("notes") if isinstance(payload.get("notes"), dict) else None
        missing_mods: List[str] = []
        if isinstance(notes_payload, dict):
            raw_missing = notes_payload.get("missing_mods")
            if isinstance(raw_missing, list):
                missing_mods = [str(entry) for entry in raw_missing if isinstance(entry, str) and entry.strip()]
        logged_at_value = payload.get("logged_at")
        return ExecutedPlanRecord(
            plan_id=normalized,
            summary=str(payload.get("summary") or ""),
            status=str(payload.get("status") or "unknown"),
            commands=commands,
            mod_hooks=mod_hooks,
            logged_at=logged_at_value if isinstance(logged_at_value, str) else None,
            player_pose=player_pose,
            location=location,
            log_path=path,
            missing_mods=missing_mods,
        )

    def _normalize_plan_id(self, plan_id: str) -> str:
        cleaned = (plan_id or "").strip()
        if not cleaned:
            raise ValueError("plan_id is required")
        if cleaned.lower().endswith(".json"):
            cleaned = cleaned[:-5]
        if not cleaned:
            raise ValueError("plan_id is required")
        return cleaned

    def _extract_plan_location(
        self,
        commands: List[str],
        player_pose: Optional[PlayerPose],
    ) -> Optional[PlanLocation]:
        for command in commands:
            match = _EXECUTE_LOCATION_PATTERN.search(command)
            if match:
                try:
                    world = match.group("world")
                    x = float(match.group("x"))
                    y = float(match.group("y"))
                    z = float(match.group("z"))
                except Exception:
                    continue
                return PlanLocation(world=world, x=x, y=y, z=z)
        if player_pose is not None:
            return PlanLocation(
                world=player_pose.world,
                x=player_pose.x,
                y=player_pose.y,
                z=player_pose.z,
            )
        return None

    def ingest_narrative_event(self, event: NarrativeChatEvent) -> NarrativeIngestionResponse:
        scenario_id = event.scenario_id or "default"
        extraction = self._narrative_ingestor.process(event)

        response_status = "accepted"
        message: Optional[str] = None

        if not extraction.has_core_fields:
            first_paragraph = event.message.strip().splitlines()[0].strip() if event.message.strip() else ""
            is_meaningful = len(first_paragraph) >= 8
            if is_meaningful:
                submission = DeviceSpecSubmission(
                    player_id=event.player_id,
                    narrative=event.message.strip(),
                    scenario_id=scenario_id,
                    is_draft=True,
                    logic_outline=[first_paragraph],
                )
                result = self.submit(submission)
                return NarrativeIngestionResponse(
                    status="needs_review",
                    confidence=extraction.confidence,
                    missing_fields=[field for field in extraction.missing_fields if field in {"vision", "actions", "resources", "location"}],
                    message="未找到结构化标签，已作为草稿保送，请在 CityPhone 完善字段。",
                    source_fields=extraction.raw_fields,
                    submission=submission.model_dump(mode="json"),
                    ruling=result.ruling.model_dump(mode="json"),
                    notice=result.notice.model_dump(mode="json"),
                    guidance=[item.model_dump(mode="json") for item in result.guidance],
                    build_plan=result.build_plan.model_dump(mode="json") if result.build_plan else None,
                    state=self.cityphone_state(event.player_id, scenario_id).model_dump(mode="json"),
                )
            response_status = "rejected"
            message = "缺少愿景或行动，未提交裁决。"
            return NarrativeIngestionResponse(
                status=response_status,
                confidence=extraction.confidence,
                missing_fields=extraction.missing_fields,
                message=message,
                source_fields=extraction.raw_fields,
            )

        submission = DeviceSpecSubmission(
            player_id=event.player_id,
            narrative=event.message.strip(),
            scenario_id=scenario_id,
            is_draft=extraction.needs_manual_review,
            world_constraints=extraction.constraints,
            logic_outline=extraction.actions,
            success_criteria=extraction.success,
            risk_register=extraction.risks,
            resource_ledger=extraction.resources,
            player_pose=extraction.pose,
        )

        result = self.submit(submission)

        if extraction.needs_manual_review:
            response_status = "needs_review"
            message = "已作为草稿提交，建议使用 CityPhone 补齐缺失字段。"
        else:
            message = "已自动提交裁决。"

        return NarrativeIngestionResponse(
            status=response_status,
            confidence=extraction.confidence,
            missing_fields=extraction.missing_fields,
            message=message,
            source_fields=extraction.raw_fields,
            submission=submission.model_dump(mode="json"),
            ruling=result.ruling.model_dump(mode="json"),
            notice=result.notice.model_dump(mode="json"),
            guidance=[item.model_dump(mode="json") for item in result.guidance],
            build_plan=result.build_plan.model_dump(mode="json") if result.build_plan else None,
            state=self.cityphone_state(event.player_id, scenario_id).model_dump(mode="json"),
        )

    def social_atmosphere(self, limit: int = 5) -> SocialAtmospherePayload:
        return self._social_repo.load_atmosphere(limit=limit)

    def submit(self, submission: DeviceSpecSubmission) -> SubmissionResult:
        intent_match = detect_intent(submission.narrative)
        if intent_match and intent_match.kind == IntentKind.REFRESH_MODS:
            return self._process_mod_refresh(submission)
        scenario_id = submission.scenario_id or "default"
        scenario = self._scenario_repo.load(scenario_id)
        spec = submission.to_spec(self._spec_normalizer, scenario)
        if spec.scenario_id != scenario.scenario_id:
            scenario = self._scenario_repo.load(spec.scenario_id)
        story_outcome = self._story_manager.process(
            player_id=submission.player_id,
            scenario_id=scenario.scenario_id,
            scenario=scenario,
            spec=spec,
            narrative=submission.narrative,
            player_pose=submission.player_pose,
        )
        spec = story_outcome.enriched_spec
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
        guidance_items = self._merge_guidance(guidance_items, story_outcome.guidance)
        guidance_lines = render_guidance_text(guidance_items)

        explanation_line = self._explainer.build_explanation(ruling.verdict, guidance_lines)
        if explanation_line and explanation_line not in ruling.reasoning:
            ruling.reasoning.append(explanation_line)

        plan: Optional[BuildPlan] = None
        plan_snapshot: Optional[BuildPlanSnapshot] = None
        if story_outcome.ready_for_build:
            plan_ctx = BuildPlanContext(
                spec=envelope.spec,
                ruling=ruling,
                scenario=scenario,
                story_state=story_outcome.state,
            )
            plan = self._build_plan_agent.generate(plan_ctx)
            if plan is not None:
                if plan.mod_hooks:
                    valid_mods = [hook for hook in plan.mod_hooks if self._mod_manager.has_mod(hook)]
                    plan = plan.model_copy(update={"mod_hooks": valid_mods})
                pose = submission.player_pose or story_outcome.state.player_pose
                if pose is not None:
                    plan.player_pose = pose
                location_hint = self._estimate_location(plan)
                plan_snapshot = BuildPlanSnapshot(
                    plan_id=str(plan.plan_id),
                    summary=plan.summary,
                    steps=[f"{step.step_id}: {step.title}" for step in plan.steps],
                    mod_hooks=plan.mod_hooks,
                    player_pose=plan.player_pose,
                    location_hint=location_hint,
                )
                self._scheduler.enqueue(plan)
        else:
            if story_outcome.missing_slots:
                waiting_hint = "建造排程暂缓：等待补齐→ " + "；".join(story_outcome.missing_slots.values())
                context_notes.append(waiting_hint)

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

    def cityphone_state(self, player_id: str, scenario_id: Optional[str] = None) -> CityPhoneStatePayload:
        scenario_id = scenario_id or "default"
        state = self._story_repository.load(player_id, scenario_id)
        if state is None:
            state = StoryState(player_id=player_id, scenario_id=scenario_id)

        latest_entry = self._repository.latest_for_player(player_id)
        plan_obj: Optional[BuildPlan] = None
        executed_record: Optional[ExecutedPlanRecord] = None
        if latest_entry:
            _, notice = latest_entry
            if notice.build_plan and notice.build_plan.plan_id:
                plan_obj = self._repository.get_plan(notice.build_plan.plan_id)
                if plan_obj:
                    executed_record = self.fetch_executed_plan(str(plan_obj.plan_id))
                    if executed_record is not None:
                        state = self._story_manager.sync_execution_feedback(
                            player_id=player_id,
                            scenario_id=scenario_id,
                            plan_id=str(plan_obj.plan_id),
                            status=executed_record.status,
                            command_count=len(executed_record.commands or []),
                            missing_mods=executed_record.missing_mods,
                            summary=plan_obj.summary,
                            log_path=str(executed_record.log_path) if executed_record.log_path else None,
                        )

        phase = determine_phase(state)
        ready = state.ready_for_build

        def _plan_status_label(raw: str) -> str:
            mapping = {
                "completed": "已完成",
                "running": "执行中",
                "queued": "已入队",
                "pending": "待处理",
                "blocked": "受阻",
            }
            key = (raw or "").lower()
            return mapping.get(key, raw or "未知")

        notes_tail = state.notes[-4:]
        vision_panel = CityPhoneVisionPanel(
            goals=state.goals,
            logic_outline=state.logic_outline,
            open_questions=state.open_questions,
            notes=notes_tail,
            coverage=state.coverage or {},
        )

        resources_panel = CityPhoneResourcesPanel(
            items=state.resources,
            pending=not bool(state.resources),
            risk_register=state.risk_register or [],
            risk_pending=not bool(state.risk_register),
        )

        location_quality: Optional[str]
        if state.player_pose is not None:
            location_quality = "坐标已同步"
        elif state.location_hint:
            location_quality = "已有地标提示，待同步坐标"
        else:
            location_quality = "缺少地标提示"

        location_panel = CityPhoneLocationPanel(
            location_hint=state.location_hint,
            player_pose=state.player_pose,
            pending=state.player_pose is None,
            location_quality=location_quality,
        )

        plan_panel = CityPhonePlanPanel(
            available=False,
            summary=None,
            steps=[],
            mod_hooks=[],
            plan_id=str(plan_obj.plan_id) if plan_obj else None,
            status=_plan_status_label("blocked" if not ready else "pending"),
            pending_reasons=state.blocking if not ready else [],
        )
        if plan_obj:
            plan_status_raw = plan_obj.status.value
            plan_notes: List[str] = []
            if executed_record is not None:
                if executed_record.status:
                    plan_status_raw = executed_record.status
                command_count = len(executed_record.commands or [])
                if command_count:
                    plan_notes.append(f"建造指令已派发 {command_count} 条。")
                else:
                    plan_notes.append("发现建造记录但未写入具体指令，检查执行器日志。")
                if executed_record.missing_mods:
                    mods_text = ", ".join(sorted(executed_record.missing_mods))
                    plan_notes.append(f"缺少模组：{mods_text}。")
                if executed_record.status and executed_record.status != "completed":
                    plan_notes.append(f"建造状态：{_plan_status_label(executed_record.status)}。")
                if executed_record.log_path:
                    plan_notes.append(f"日志文件：{executed_record.log_path.name}")
            else:
                if plan_obj.status == BuildPlanStatus.queued:
                    plan_notes.append("计划已排队，等待建造执行器处理。")
            if not ready and state.blocking:
                plan_notes.extend(state.blocking)
            if plan_notes:
                deduped: List[str] = []
                seen_notes: set[str] = set()
                for entry in plan_notes:
                    text = str(entry).strip()
                    if not text or text in seen_notes:
                        continue
                    seen_notes.add(text)
                    deduped.append(text)
                plan_notes = deduped
            plan_panel = CityPhonePlanPanel(
                available=True,
                summary=plan_obj.summary,
                steps=[f"{step.step_id}: {step.title}" for step in plan_obj.steps],
                mod_hooks=plan_obj.mod_hooks,
                plan_id=str(plan_obj.plan_id),
                status=_plan_status_label(plan_status_raw),
                pending_reasons=plan_notes,
            )
        elif ready:
            plan_panel = CityPhonePlanPanel(
                available=False,
                summary=None,
                steps=[],
                mod_hooks=[],
                plan_id=None,
                status=_plan_status_label("pending"),
                pending_reasons=["档案馆未能找到最近的建造计划，请重新提交叙述。"],
            )

        panels = CityPhonePanels(
            vision=vision_panel,
            resources=resources_panel,
            location=location_panel,
            plan=plan_panel,
        )

        return CityPhoneStatePayload(
            player_id=player_id,
            scenario_id=scenario_id,
            phase=phase,
            ready_for_build=ready,
            build_capability=state.build_capability,
            motivation_score=state.motivation_score,
            logic_score=state.logic_score,
            blocking=state.blocking or [],
            panels=panels,
        )

    def handle_cityphone_action(self, payload: CityPhoneAction) -> CityPhoneActionResult:
        scenario_id = payload.scenario_id or "default"
        player_id = payload.player_id
        action = payload.action.lower().strip()

        if action in {"request_state", "state"}:
            state = self.cityphone_state(player_id, scenario_id)
            return CityPhoneActionResult(status="ok", state=state, message="已同步当前状态。")

        if action == "submit_narrative":
            narrative = str(payload.payload.get("narrative") or "").strip()
            if not narrative:
                state = self.cityphone_state(player_id, scenario_id)
                return CityPhoneActionResult(
                    status="error",
                    state=state,
                    error="missing_narrative",
                    message="请先填写要记录的内容。",
                )
            pose_data = payload.payload.get("pose")
            player_pose: Optional[PlayerPose] = None
            if isinstance(pose_data, dict):
                try:
                    player_pose = PlayerPose.model_validate(pose_data)
                except Exception:
                    player_pose = None
            submission = DeviceSpecSubmission(
                player_id=player_id,
                narrative=narrative,
                scenario_id=scenario_id,
                player_pose=player_pose,
            )
            result = self.submit(submission)
            state = self.cityphone_state(player_id, scenario_id)
            notice_payload = result.notice.model_dump(mode="json")
            plan_payload = result.build_plan.model_dump(mode="json") if result.build_plan else None
            guidance_payload = [item.model_dump(mode="json") for item in result.guidance]
            return CityPhoneActionResult(
                status="ok",
                state=state,
                notice=notice_payload,
                build_plan=plan_payload,
                guidance=guidance_payload,
                message="已记录新的叙述。",
            )

        if action == "push_pose":
            pose_data = payload.payload.get("pose")
            if not isinstance(pose_data, dict):
                state = self.cityphone_state(player_id, scenario_id)
                return CityPhoneActionResult(
                    status="error",
                    state=state,
                    error="missing_pose",
                    message="未提供坐标信息。",
                )
            try:
                pose = PlayerPose.model_validate(pose_data)
            except Exception:
                state = self.cityphone_state(player_id, scenario_id)
                return CityPhoneActionResult(
                    status="error",
                    state=state,
                    error="invalid_pose",
                    message="坐标格式无法识别。",
                )
            location_hint = payload.payload.get("location_hint")
            if isinstance(location_hint, str):
                location_hint = location_hint.strip() or None
            else:
                location_hint = None
            self._story_manager.apply_pose_update(
                player_id=player_id,
                scenario_id=scenario_id,
                pose=pose,
                location_hint=location_hint,
            )
            state = self.cityphone_state(player_id, scenario_id)
            return CityPhoneActionResult(
                status="ok",
                state=state,
                message="坐标已同步。",
            )

        if action == "apply_template":
            template_value = payload.payload.get("template") if isinstance(payload.payload, dict) else None
            template_key = str(template_value).strip() if template_value is not None else ""
            result = self._story_manager.apply_template(
                player_id=player_id,
                scenario_id=scenario_id,
                template_key=template_key,
            )
            state = self.cityphone_state(player_id, scenario_id)
            if result.applied:
                return CityPhoneActionResult(
                    status="ok",
                    state=state,
                    message=result.message,
                )
            return CityPhoneActionResult(
                status="error",
                state=state,
                error=result.reason or "template_failed",
                message=result.message,
            )

        state = self.cityphone_state(player_id, scenario_id)
        return CityPhoneActionResult(
            status="error",
            state=state,
            error="unknown_action",
            message="暂不支持该动作。",
        )

    def _estimate_location(self, plan: BuildPlan) -> Optional[PlanLocation]:
        pose = plan.player_pose
        if pose is None:
            return None
        distance = 6.0
        yaw_rad = math.radians(pose.yaw)
        x = pose.x - math.sin(yaw_rad) * distance
        z = pose.z + math.cos(yaw_rad) * distance
        return PlanLocation(world=pose.world, x=x, y=pose.y, z=z)

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
    def _merge_guidance(
        existing: List[GuidanceItem],
        additions: List[GuidanceItem],
    ) -> List[GuidanceItem]:
        if not additions:
            return existing
        merged: List[GuidanceItem] = list(existing)
        seen = {item.text for item in existing}
        for item in additions:
            if item.text in seen:
                continue
            merged.append(item)
            seen.add(item.text)
        return merged

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