"""Ideal City minimal submission → adjudication → execution pipeline.

This module wires the semantic DeviceSpec objects to world-sovereign adjudication
and execution notices while strictly upholding guardrails:
- No direct world patches or plugin callbacks.
- No algorithmic scoring engines or task fallbacks.
- All state changes occur in backend-owned storage under backend/data/ideal_city.
"""

from __future__ import annotations

import logging
import json
import math
import os
from dataclasses import dataclass
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict

from .adjudication_contract import (
    AdjudicationRecord,
    VerdictEnum,
    freeze_for_history as freeze_ruling,
)
from .exhibit_narrative import ExhibitNarrative, ExhibitNarrativeRepository
from .device_spec import (
    DeviceSpec,
    DeviceSpecEnvelope,
    freeze_for_history as freeze_spec,
    sanitize_lines,
)
from .build_plan import BuildPlan, PlayerPose
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
from .social_feedback import SocialFeedbackRepository, SocialAtmospherePayload
from .manifestation_intent import ManifestationIntent
from .manifestation_writer import ManifestationIntentWriter
from .technology_status import (
    TechnologyEvent,
    TechnologyStatusRepository,
    TechnologyStatusSnapshot,
)
from .exhibit_mode import ExhibitMode, ExhibitModeResolver, ExhibitModeState
from app.core.story.exhibit_instance_repository import ExhibitInstanceRepository, ExhibitInstance


_EXECUTE_LOCATION_PATTERN = re.compile(
    r"execute\s+in\s+(?P<world>[^\s]+)\s+positioned\s+(?P<x>-?\d+(?:\.\d+)?)\s+(?P<y>-?\d+(?:\.\d+)?)\s+(?P<z>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


if TYPE_CHECKING:
    from .spec_normalizer import NormalizedSpec


logger = logging.getLogger(__name__)


_COVERAGE_LABELS = {
    "logic_outline": "执行逻辑",
    "world_constraints": "世界约束",
    "resource_ledger": "资源清单",
    "success_criteria": "成功标准",
    "risk_register": "风险登记",
}

_ARCHIVE_BLACKLIST = {
    "希望",
    "期待",
    "建议",
    "应当",
    "需要",
    "可以",
    "补齐",
    "完善",
    "改进",
    "优化",
    "生成",
    "执行",
    "计划",
    "步骤",
    "字段",
    "解锁",
    "进入",
    "准备就绪",
    "下一阶段",
    "待补充",
    "需补",
}


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
    manifestation_intent: Optional[ManifestationIntent] = None


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


class CityPhoneNarrativeSection(BaseModel):
    slot: str
    title: str
    body: List[str] = Field(default_factory=list)
    accent: Optional[str] = None


class CityPhoneNarrativePayload(BaseModel):
    mode: str = "archive"
    title: Optional[str] = None
    timeframe: Optional[str] = None
    last_event: Optional[str] = None
    sections: List[CityPhoneNarrativeSection] = Field(default_factory=list)


@dataclass
class NarrativeBundle:
    narrative: CityPhoneNarrativePayload
    city_interpretation: List[str]
    unknowns: List[str]
    history_entries: List[str]


class ExhibitModeView(BaseModel):
    label: str = "看展模式 · Archive"
    description: List[str] = Field(default_factory=list)

    @classmethod
    def from_state(cls, state: ExhibitModeState) -> "ExhibitModeView":
        label = state.label or "看展模式 · Archive"
        description = [line for line in (state.description or []) if line.strip()]
        return cls(label=label, description=description)

    model_config = ConfigDict(extra="forbid")


class CityPhoneExhibitInstanceView(BaseModel):
    instance_id: str
    snapshot_type: str
    created_at: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


class CityPhoneExhibitsPayload(BaseModel):
    instances: List[CityPhoneExhibitInstanceView] = Field(default_factory=list)


class CityPhoneStatePayload(BaseModel):
    city_interpretation: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    history_entries: List[str] = Field(default_factory=list)
    narrative: CityPhoneNarrativePayload = Field(default_factory=CityPhoneNarrativePayload)
    exhibit_mode: ExhibitModeView = Field(default_factory=ExhibitModeView)
    exhibits: CityPhoneExhibitsPayload = Field(default_factory=CityPhoneExhibitsPayload)

    model_config = ConfigDict(extra="forbid")


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
    manifestation_intent: Optional[dict] = None
    error: Optional[str] = None
    message: Optional[str] = None
    city_interpretation: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    interpretation_delays: List[str] = Field(default_factory=list)
    exhibit_mode: Optional[ExhibitModeView] = None


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
            reasoning.append("缺少必要结构：" + "、".join(missing_sections) + "，需补齐后再提交。")
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
        protocol_override = os.getenv("IDEAL_CITY_PROTOCOL_ROOT")
        if protocol_override:
            protocol_root = Path(protocol_override).expanduser()
        else:
            protocol_root = data_dir / "protocol"
        self._protocol_root = protocol_root
        self._social_repo = SocialFeedbackRepository(protocol_root)
        self._manifestation_writer = ManifestationIntentWriter(protocol_root)
        self._tech_status_repo = TechnologyStatusRepository(protocol_root)
        exhibits_root = data_dir / "exhibits"
        self._exhibit_repo = ExhibitNarrativeRepository(exhibits_root)
        self._exhibit_instance_repo = ExhibitInstanceRepository()
        self._mode_resolver = ExhibitModeResolver()

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
                    manifestation_intent=(
                        result.manifestation_intent.model_dump(mode="json")
                        if result.manifestation_intent
                        else None
                    ),
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
            manifestation_intent=(
                result.manifestation_intent.model_dump(mode="json")
                if result.manifestation_intent
                else None
            ),
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

        manifestation_intent: Optional[ManifestationIntent] = None
        if story_outcome.ready_for_build and ruling.verdict == VerdictEnum.ACCEPT:
            manifestation_intent = self._issue_manifestation_intent(
                player_id=submission.player_id,
                spec_id=spec.spec_id,
                scenario=scenario,
                state=story_outcome.state,
                context_notes=context_notes,
                guidance_lines=guidance_lines,
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
            manifestation_intent=manifestation_intent,
        )

    def cityphone_state(self, player_id: str, scenario_id: Optional[str] = None) -> CityPhoneStatePayload:
        scenario_id = scenario_id or "default"
        state = self._story_repository.load(player_id, scenario_id)
        if state is None:
            state = StoryState(player_id=player_id, scenario_id=scenario_id)

        scenario = self._scenario_repo.load(scenario_id)

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

        technology_status_snapshot = self._tech_status_repo.load_snapshot()
        mode_state = self._mode_resolver.resolve(
            has_active_plan=bool(plan_obj is not None),
            has_execution_record=executed_record is not None,
        )
        exhibit_mode_view = ExhibitModeView.from_state(mode_state)
        exhibit_mode_view.description = [
            "展馆当前处于档案展示状态。",
            "内容用于回顾与理解历史文本，而非指导行为。",
        ]

        base_narrative = self._exhibit_repo.load(scenario_id)
        narrative_bundle = self._compose_narrative(
            scenario=scenario,
            base=base_narrative,
            state=state,
            executed_plan=executed_record,
            technology_status=technology_status_snapshot,
            mode_state=mode_state,
        )

        return CityPhoneStatePayload(
            city_interpretation=narrative_bundle.city_interpretation,
            unknowns=narrative_bundle.unknowns,
            history_entries=narrative_bundle.history_entries,
            narrative=narrative_bundle.narrative,
            exhibit_mode=exhibit_mode_view,
            exhibits=self._build_exhibits_payload(scenario_id=scenario_id),
        )

    def _build_exhibits_payload(self, *, scenario_id: str) -> CityPhoneExhibitsPayload:
        try:
            instances = self._exhibit_instance_repo.list_instances(scenario_id=scenario_id)
        except Exception:
            instances = []
        if not instances:
            return CityPhoneExhibitsPayload()

        ordered = sorted(
            instances,
            key=lambda inst: (inst.created_at or ""),
            reverse=True,
        )
        views: List[CityPhoneExhibitInstanceView] = []
        for inst in ordered[:8]:
            created_at = inst.created_at if isinstance(inst.created_at, str) else None
            snapshot_type = inst.snapshot_type if isinstance(inst.snapshot_type, str) else "world_patch"
            title = inst.title if isinstance(inst.title, str) else None
            description = inst.description if isinstance(inst.description, str) else None
            views.append(
                CityPhoneExhibitInstanceView(
                    instance_id=inst.instance_id,
                    snapshot_type=snapshot_type,
                    created_at=created_at,
                    title=title,
                    description=description,
                )
            )
        return CityPhoneExhibitsPayload(instances=views)

    def _compose_narrative(
        self,
        *,
        scenario: ScenarioContext,
        base: ExhibitNarrative,
        state: StoryState,
        executed_plan: Optional[ExecutedPlanRecord],
        technology_status: Optional[TechnologyStatusSnapshot],
        mode_state: ExhibitModeState,
    ) -> NarrativeBundle:
        technology_status = technology_status or TechnologyStatusSnapshot()
        title = self._clean_text(base.title) or scenario.title or scenario.scenario_id
        timeframe = self._clean_text(base.timeframe)
        if not timeframe:
            timeframe = "熄灯区纪元 · 第17周"

        gallery_status = self._build_gallery_status(timeframe=timeframe, scenario_title=scenario.title)
        overview_lines, interpretation_section = self._build_city_interpretation_view(
            scenario=scenario,
            base=base,
            state=state,
        )

        topics = self._collect_unknown_topics(
            base=base,
            state=state,
            technology_status=technology_status,
        )
        unknown_lines = self._render_unknowns_full(topics)
        open_question_lines = self._render_open_questions_section(topics)

        history_entries = self._build_history_entries(
            base=base,
            state=state,
            technology_status=technology_status,
            executed_plan=executed_plan,
        )
        history_section = self._build_history_section()

        appendix_lines = self._build_archive_appendix(base.appendix or {})

        sections: List[CityPhoneNarrativeSection] = []
        if gallery_status:
            sections.append(
                CityPhoneNarrativeSection(
                    slot="gallery_status",
                    title="展馆状态",
                    body=gallery_status,
                    accent="collecting",
                )
            )
        if interpretation_section:
            sections.append(
                CityPhoneNarrativeSection(
                    slot="city_interpretation",
                    title="来源说明",
                    body=interpretation_section,
                )
            )
        if open_question_lines:
            sections.append(
                CityPhoneNarrativeSection(
                    slot="open_questions",
                    title="记忆空白",
                    body=open_question_lines,
                )
            )
        if history_section:
            sections.append(
                CityPhoneNarrativeSection(
                    slot="history_log",
                    title="历史注记",
                    body=history_section,
                )
            )
        if appendix_lines:
            sections.append(
                CityPhoneNarrativeSection(
                    slot="archive_appendix",
                    title="档案附注",
                    body=appendix_lines,
                )
            )

        narrative = CityPhoneNarrativePayload(
            mode=mode_state.mode.value if hasattr(mode_state.mode, "value") else (mode_state.mode or "archive"),
            title=title,
            timeframe=timeframe,
            last_event=self._render_last_event(state, technology_status),
            sections=sections,
        )

        return NarrativeBundle(
            narrative=narrative,
            city_interpretation=overview_lines,
            unknowns=unknown_lines,
            history_entries=history_entries,
        )

    def _dedupe_lines(self, values: Iterable[str]) -> List[str]:
        ordered: List[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = self._clean_text(value)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            ordered.append(cleaned)
        return ordered

    def _build_gallery_status(self, *, timeframe: Optional[str], scenario_title: Optional[str]) -> List[str]:
        lines: List[str] = [
            "当前展馆以档案形式开放。",
            "此阶段侧重呈现既有记录与未解读的片段。",
            "观众可通过现存文字了解当时的讨论氛围。",
        ]
        if timeframe:
            lines.append(f"展期：{timeframe}。")
        if scenario_title:
            lines.append(f"展厅主题：{scenario_title}。")
        return self._dedupe_lines(lines)

    def _build_city_interpretation_view(
        self,
        *,
        scenario: ScenarioContext,
        base: ExhibitNarrative,
        state: StoryState,
    ) -> Tuple[List[str], List[str]]:
        # Source-focused overview: each sentence names original archival material instead of synthesising conclusions.
        overview_lines: List[str] = [
            "2056-06-12 熄灯区居民委员会提交的构想稿是此展品最早的记录，原件以手写扫描件形式存档。",
            "2056-06-18 城市工坊联盟随信附上的工具清单被标注为“物资背景”附件，完整文字收录于此。",
            "2056-06-20 巡夜护卫队会议纪要中的“夜间开放”段落以会议节选形式保存，注明了记录员。",
            "旧电车站访谈摘要与夜市摊主、学校递交的佐证文本共同构成口述来源，并列陈列于展柜。",
        ]
        author_line = self._author_context_line(state)
        if author_line:
            overview_lines.append(author_line)

        section_lines: List[str] = [
            "展柜列出了各份文本的撰写主体、日期与保存介质，供读者核查来源。",
            "“能源”“安全”等标签来源于原稿批注，未经过再解释或重写。",
            "所有记录以原始序列并列呈现，供对比不同叙述的差异。",
        ]

        return self._dedupe_lines(overview_lines), self._dedupe_lines(section_lines)

    def _author_context_line(self, state: StoryState) -> Optional[str]:
        if state.notes or state.goals or state.resources:
            return "以下内容保留了一段作者留下的原始叙述，来源标注为提交者当时的写作记录。"
        return None

    def _collect_unknown_topics(
        self,
        *,
        base: ExhibitNarrative,
        state: StoryState,
        technology_status: TechnologyStatusSnapshot,
    ) -> List[str]:
        inputs: List[str] = []
        inputs.extend(base.archive_state or [])
        inputs.extend(base.unresolved_risks or [])
        inputs.extend(base.historic_notes or [])
        # Player提交的即时叙述不应反哺“未知”列表，避免根据当次提交生成新的理解标签。
        for alert in technology_status.risk_alerts or []:
            summary = self._clean_text(alert.summary) or alert.risk_id
            if summary:
                inputs.append(summary)

        topics: List[str] = []
        seen: set[str] = set()
        for raw in inputs:
            topic = self._normalize_gap_topic(raw)
            if not topic:
                continue
            topic = self._refine_topic(topic)
            if topic in seen:
                continue
            seen.add(topic)
            topics.append(topic)

        if not topics:
            topics = [
                "夜间能源调度试运行阶段",
                "社区轮值制度",
                "工坊安全巡检记录",
                "夜间噪音议题",
                "技术监控提示",
            ]

        return topics

    def _render_unknowns_full(self, topics: List[str]) -> List[str]:
        formatted = [self._format_topic_label(topic) for topic in topics]
        templates = [
            lambda t: f"城市档案中尚未形成对{t}的整理文本，不同来源的记述存在差异。",
            lambda t: f"{t}的记忆较为零散，目前未还原出一致的书面版本。",
            lambda t: f"现存资料中缺乏针对{t}的统一说明。",
            lambda t: f"部分档案提及{t}，但相关描述未形成稳定文本。",
            lambda t: f"围绕{t}的背景说明在现有档案中仍然模糊。",
        ]
        rendered: List[str] = []
        for idx, topic in enumerate(formatted[: len(templates)]):
            rendered.append(templates[idx](topic))
        return rendered

    def _render_open_questions_section(self, topics: List[str]) -> List[str]:
        formatted = [self._format_topic_label(topic) for topic in topics]
        templates = [
            lambda t: f"{t}的记载仍存在明显缺口。",
            lambda t: f"有关{t}的描述未能在档案中完整呈现。",
            lambda t: f"部分围绕{t}的讨论上下文已在时间中遗失。",
        ]
        lines: List[str] = []
        for idx, topic in enumerate(formatted[: len(templates)]):
            lines.append(templates[idx](topic))
        return lines

    def _build_history_entries(
        self,
        *,
        base: ExhibitNarrative,
        state: StoryState,
        technology_status: TechnologyStatusSnapshot,
        executed_plan: Optional[ExecutedPlanRecord],
    ) -> List[str]:
        entries: List[str] = [
            "2056-06-12：熄灯区居民委员会递交的构想文本被归档，作为这组展品的起始记录。",
            "2056-06-18：城市工坊联盟提供的工具清单随信附上并入档，形成了物资背景的文字注记。",
            "2056-06-20：巡夜护卫队会议纪要节选被收录，用以记录“夜间开放”议题的讨论方式。",
        ]

        resident_line = self._resident_reflection_line(state)
        if resident_line:
            entries.append(resident_line)

        last_event = self._pick_last_event(state.notes, technology_status)
        if last_event:
            rewritten_event = self._rewrite_last_event_entry(last_event)
            if rewritten_event:
                entries.append(rewritten_event)

        return self._dedupe_lines(entries)

    def _resident_reflection_line(self, state: StoryState) -> Optional[str]:
        if state.notes or state.goals:
            return "某次居民口述记录提到，希望把熄灯区的夜间景象写成更具活力的公共叙述。"
        return None

    def _rewrite_last_event_entry(self, last_event: str) -> Optional[str]:
        text = self._clean_text(last_event)
        if not text:
            return None
        if "·" in text:
            timestamp, description = [segment.strip() for segment in text.split("·", 1)]
        else:
            parts = text.split(" ", 1)
            if len(parts) == 2:
                timestamp, description = parts
            else:
                return None

        description_map = {
            "Forge advanced crystal technology to stage 1": "紫水晶相关技术阶段曾出现一次推进",
        }
        normalized_desc = description_map.get(description, description)
        normalized_desc = self._strip_blacklist_tokens(normalized_desc)
        return f"{timestamp}：档案中新增一则提及{normalized_desc}的注记，用以记录当时的说法。"

    def _build_history_section(self) -> List[str]:
        return [
            "档案保留了多次来自不同主体的文字与会议记录，并注明撰写时间。",
            "这些注记以原文摘录呈现，展示了展品在不同时刻的记录差异。",
            "并不构成对后续行为的指示。",
        ]

    def _build_archive_appendix(self, appendix: Dict[str, List[str]]) -> List[str]:
        lines: List[str] = []
        if appendix:
            lines.append("附注：部分相关素材（如能源表格或口述记录）曾被提及，但未完整保存。")
            lines.append("附注：现有展示内容以文字记录为主，未包含物理实施细节。")
        else:
            lines.append("附注：部分相关素材（如能源表格或口述记录）曾被提及，但未完整保存。")
            lines.append("附注：现有展示内容以文字记录为主，未包含物理实施细节。")
        return self._dedupe_lines(lines)

    def _render_last_event(self, state: StoryState, technology_status: TechnologyStatusSnapshot) -> Optional[str]:
        if state.notes or technology_status.recent_events:
            return "档案新增一条署名居民的“公共工坊”设想节选，标注来源为个人笔记。"
        return None

    def _normalize_gap_topic(self, value: str) -> Optional[str]:
        text = self._clean_text(value)
        if not text:
            return None

        text = re.sub(r"风险[:：]\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"技术告警\[[^\]]+\]\s*[:：]?", "", text)
        text = re.sub(r"(?i)plan|模板|字段|核心|提交|生成|步骤|条件|计划", "", text)
        text = re.sub(r"(?i)ready|pending|available|blocked", "", text)
        text = re.sub(r"[/\\]", "，", text)
        text = text.replace("补齐", "")
        text = text.replace("至少一个", "")
        text = text.replace("待补充", "")
        text = re.sub(r"需补[:：]?", "", text)
        text = text.strip()
        text = text.strip("：:，,。；;")
        text = re.sub(r"\s+", " ", text)
        if not text:
            return None
        if text.startswith("关于"):
            text = text[2:]
        text = re.split(r"[，,。；;]", text)[0]
        sanitized = self._strip_blacklist_tokens(text)
        return sanitized or None

    def _refine_topic(self, text: str) -> str:
        replacements = {
            "夜间能源调度仍在试运行": "夜间能源调度试运行阶段",
            "社区轮值制度尚未形成书面档案": "社区轮值制度",
            "工坊安全巡检记录缺口": "工坊安全巡检记录",
            "夜间噪音扰民": "夜间噪音议题",
            "若能源调度失衡": "技术监控提示",
        }
        for needle, replacement in replacements.items():
            if needle in text:
                return replacement
        return text

    def _format_topic_label(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("“") and cleaned.endswith("”"):
            cleaned = cleaned[1:-1]
        cleaned = cleaned.strip("「」") or text
        return f"「{cleaned}」相关记录"

    def _strip_blacklist_tokens(self, text: str) -> str:
        sanitized = text
        for token in _ARCHIVE_BLACKLIST:
            sanitized = sanitized.replace(token, "")
        sanitized = re.sub(r"\s+", " ", sanitized)
        return sanitized.strip(" ，。:：;")

    def _clean_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _translate_gap(self, field: str) -> str:
        return _COVERAGE_LABELS.get(field, field)

    def _format_event(self, event: TechnologyEvent) -> Optional[str]:
        description = self._clean_text(event.description) or self._clean_text(event.impact) or event.event_id
        timestamp: Optional[str] = None
        if event.occurred_at is not None:
            ts = event.occurred_at.astimezone(timezone.utc)
            timestamp = ts.strftime("%Y-%m-%d %H:%M")
        if timestamp and description:
            return f"{timestamp} · {description}"
        return description

    def _pick_last_event(
        self,
        notes: List[str],
        technology_status: TechnologyStatusSnapshot,
    ) -> Optional[str]:
        for entry in reversed(notes or []):
            cleaned = self._clean_text(entry)
            if cleaned:
                return cleaned
        for event in reversed(technology_status.recent_events or []):
            formatted = self._format_event(event)
            if formatted:
                return formatted
        return None

    def _extract_action_feedback(
        self, state: CityPhoneStatePayload
    ) -> Tuple[List[str], List[str], List[str]]:
        interpretation = self._dedupe_lines(state.city_interpretation or [])
        unknowns = self._dedupe_lines(state.unknowns or [])
        history = self._dedupe_lines(state.history_entries or [])
        return interpretation, [], unknowns or history

    def handle_cityphone_action(self, payload: CityPhoneAction) -> CityPhoneActionResult:
        scenario_id = payload.scenario_id or "default"
        player_id = payload.player_id
        action = payload.action.lower().strip()

        if action in {"request_state", "state"}:
            state = self.cityphone_state(player_id, scenario_id)
            interpretation, delays, unknowns = self._extract_action_feedback(state)
            return CityPhoneActionResult(
                status="ok",
                state=state,
                message="已同步当前状态。",
                city_interpretation=interpretation,
                interpretation_delays=delays,
                unknowns=unknowns,
                exhibit_mode=state.exhibit_mode,
            )

        if action == "submit_narrative":
            narrative = str(payload.payload.get("narrative") or "").strip()
            if not narrative:
                state = self.cityphone_state(player_id, scenario_id)
                interpretation, delays, unknowns = self._extract_action_feedback(state)
                return CityPhoneActionResult(
                    status="error",
                    state=state,
                    error="missing_narrative",
                    message="请先填写要记录的内容。",
                    city_interpretation=interpretation,
                    interpretation_delays=delays,
                    unknowns=unknowns,
                    exhibit_mode=state.exhibit_mode,
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
            manifestation_payload = (
                result.manifestation_intent.model_dump(mode="json")
                if result.manifestation_intent
                else None
            )
            interpretation, delays, unknowns = self._extract_action_feedback(state)
            return CityPhoneActionResult(
                status="ok",
                state=state,
                notice=notice_payload,
                build_plan=plan_payload,
                guidance=guidance_payload,
                manifestation_intent=manifestation_payload,
                message="已记录新的叙述。",
                city_interpretation=interpretation,
                interpretation_delays=delays,
                unknowns=unknowns,
                exhibit_mode=state.exhibit_mode,
            )

        if action == "push_pose":
            pose_data = payload.payload.get("pose")
            if not isinstance(pose_data, dict):
                state = self.cityphone_state(player_id, scenario_id)
                interpretation, delays, unknowns = self._extract_action_feedback(state)
                return CityPhoneActionResult(
                    status="error",
                    state=state,
                    error="missing_pose",
                    message="未提供坐标信息。",
                    city_interpretation=interpretation,
                    interpretation_delays=delays,
                    unknowns=unknowns,
                    exhibit_mode=state.exhibit_mode,
                )
            try:
                pose = PlayerPose.model_validate(pose_data)
            except Exception:
                state = self.cityphone_state(player_id, scenario_id)
                interpretation, delays, unknowns = self._extract_action_feedback(state)
                return CityPhoneActionResult(
                    status="error",
                    state=state,
                    error="invalid_pose",
                    message="坐标格式无法识别。",
                    city_interpretation=interpretation,
                    interpretation_delays=delays,
                    unknowns=unknowns,
                    exhibit_mode=state.exhibit_mode,
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
            interpretation, delays, unknowns = self._extract_action_feedback(state)
            return CityPhoneActionResult(
                status="ok",
                state=state,
                message="坐标已同步。",
                city_interpretation=interpretation,
                interpretation_delays=delays,
                unknowns=unknowns,
                exhibit_mode=state.exhibit_mode,
            )

        if action == "apply_template":
            state = self.cityphone_state(player_id, scenario_id)
            interpretation, delays, unknowns = self._extract_action_feedback(state)
            return CityPhoneActionResult(
                status="error",
                state=state,
                error="template_archived",
                message="模板功能已封存，仅供查阅。",
                city_interpretation=interpretation,
                interpretation_delays=delays,
                unknowns=unknowns,
                exhibit_mode=state.exhibit_mode,
            )

        state = self.cityphone_state(player_id, scenario_id)
        interpretation, delays, unknowns = self._extract_action_feedback(state)
        return CityPhoneActionResult(
            status="error",
            state=state,
            error="unknown_action",
            message="暂不支持该动作。",
            city_interpretation=interpretation,
            interpretation_delays=delays,
            unknowns=unknowns,
            exhibit_mode=state.exhibit_mode,
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

    def _issue_manifestation_intent(
        self,
        *,
        player_id: str,
        spec_id: str,
        scenario: ScenarioContext,
        state: StoryState,
        context_notes: List[str],
        guidance_lines: List[str],
    ) -> Optional[ManifestationIntent]:
        try:
            intent = self._build_manifestation_intent(
                scenario=scenario,
                state=state,
                context_notes=context_notes,
                guidance_lines=guidance_lines,
            )
            self._manifestation_writer.write_intent(intent, player_id=player_id, spec_id=spec_id)
            return intent
        except Exception:
            logger.exception("Failed to publish manifestation intent for spec %s", spec_id)
            return None

    def _build_manifestation_intent(
        self,
        *,
        scenario: ScenarioContext,
        state: StoryState,
        context_notes: List[str],
        guidance_lines: List[str],
    ) -> ManifestationIntent:
        allowed_stage = self._determine_allowed_stage(state)
        constraints = self._collect_manifestation_constraints(scenario, state)
        notes = self._collect_manifestation_notes(state, context_notes, guidance_lines)
        scenario_version = getattr(scenario, "scenario_version", None)
        return ManifestationIntent.create(
            scenario_id=scenario.scenario_id,
            scenario_version=scenario_version,
            allowed_stage=allowed_stage,
            constraints=constraints,
            context_notes=notes,
        )

    @staticmethod
    def _determine_allowed_stage(state: StoryState) -> int:
        if state.build_capability >= 120:
            return 2
        return 1

    def _collect_manifestation_constraints(self, scenario: ScenarioContext, state: StoryState) -> List[str]:
        entries: List[str] = ["no_stage_skip"]
        entries.extend(scenario.contextual_constraints or [])
        entries.extend(state.world_constraints or [])
        return self._dedupe_strings(entries)

    def _collect_manifestation_notes(
        self,
        state: StoryState,
        context_notes: List[str],
        guidance_lines: List[str],
    ) -> List[str]:
        entries: List[str] = []
        seen: set[str] = set()

        def _append(values: Iterable[str]) -> None:
            for value in values:
                text = str(value).strip()
                if not text or text in seen:
                    continue
                entries.append(text)
                seen.add(text)
                if len(entries) >= 8:
                    return

        _append(context_notes)
        _append(guidance_lines)
        if state.success_criteria:
            _append(state.success_criteria)
        if state.location_hint:
            _append([f"施工地标：{state.location_hint}"])
        elif state.player_pose is not None:
            pose = state.player_pose
            pose_note = f"玩家坐标 {pose.world} @ {pose.x:.2f}, {pose.y:.2f}, {pose.z:.2f}"
            _append([pose_note])
        if not entries:
            entries.append("档案馆确认：该方案可进入熄灯区试点阶段。")
        return entries

    @staticmethod
    def _dedupe_strings(values: Iterable[str]) -> List[str]:
        result: List[str] = []
        seen: set[str] = set()
        for entry in values:
            text = str(entry).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

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