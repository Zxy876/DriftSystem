"""Intent recognition and planning endpoints for chat-driven creation."""

from __future__ import annotations

from typing import Dict, List, Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.creation import CreationPlanResult
from app.services import creation_workflow


class IntentRecognizeRequest(BaseModel):
    message: str = Field(..., description="玩家发送的原始聊天内容")


class CreationSlots(BaseModel):
    actions: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)


class IntentRecognizeResponse(BaseModel):
    is_creation: bool
    confidence: float
    reasons: List[str] = Field(default_factory=list)
    creation_slots: CreationSlots = Field(default_factory=CreationSlots)
    raw_slots: Dict[str, List[str]] = Field(default_factory=dict, description="调试用途，保留原始匹配结果")


router = APIRouter(prefix="/intent", tags=["Intent"])


@router.post("/recognize", response_model=IntentRecognizeResponse)
def recognize_intent(payload: IntentRecognizeRequest) -> IntentRecognizeResponse:
    decision = creation_workflow.classify_message(payload.message)
    slots: Dict[str, List[str]] = {}
    for key, value in decision.slots.items():
        slots[key] = [str(item) for item in value]

    creation_slots = CreationSlots(
        actions=slots.get("actions", []),
        materials=slots.get("materials", []),
    )
    return IntentRecognizeResponse(
        is_creation=decision.is_creation,
        confidence=decision.confidence,
        reasons=decision.reasons,
        creation_slots=creation_slots,
        raw_slots=slots,
    )


class CreationPlanMaterialModel(BaseModel):
    token: str
    resource_id: Optional[str] = None
    label: Optional[str] = None
    status: str
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    quantity: int = Field(0, ge=0)
    tags: List[str] = Field(default_factory=list)


class CreationPlanStepModel(BaseModel):
    step_id: str
    title: str
    description: str
    status: str
    step_type: str
    commands: List[str] = Field(default_factory=list)
    required_resource: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class CreationPatchTemplateModel(BaseModel):
    step_id: str
    template_id: str
    status: str
    summary: str
    step_type: str
    world_patch: Dict[str, object] = Field(default_factory=dict)
    mod_hooks: List[str] = Field(default_factory=list)
    requires_player_pose: bool = False
    notes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    validation: Dict[str, object] = Field(default_factory=dict)


class CreationPlanResponse(BaseModel):
    action: Optional[str]
    confidence: float
    summary: str
    materials: List[CreationPlanMaterialModel] = Field(default_factory=list)
    steps: List[CreationPlanStepModel] = Field(default_factory=list)
    patch_templates: List[CreationPatchTemplateModel] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    unresolved_tokens: List[str] = Field(default_factory=list)
    execution_tier: str
    validation_errors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    unsafe_steps: List[str] = Field(default_factory=list)
    safety_assessment: Dict[str, object] = Field(default_factory=dict)
    snapshot_generated_at: Optional[str] = None


class CreationExecuteRequest(BaseModel):
    message: str = Field(..., description="玩家发送的原始聊天内容")
    player_id: Optional[str] = Field(default=None, description="用于打标签的玩家标识")
    dry_run_only: bool = Field(False, description="仅执行 dry-run，不触发真实命令")


class CreationExecuteResponse(BaseModel):
    status: Literal["ok", "not_creation", "dry_run"]
    decision: Dict[str, object]
    plan: Optional[CreationPlanResponse] = None
    report: Optional[Dict[str, object]] = None


@router.post("/plan", response_model=CreationPlanResponse)
def generate_creation_plan(payload: IntentRecognizeRequest) -> CreationPlanResponse:
    decision = creation_workflow.classify_message(payload.message)
    plan_result: CreationPlanResult = creation_workflow.generate_plan(decision, message=payload.message)
    plan_payload = plan_result.plan.to_payload()

    materials = [
        CreationPlanMaterialModel(**material)  # type: ignore[arg-type]
        for material in plan_payload.get("materials", [])
    ]
    steps = [
        CreationPlanStepModel(**step)  # type: ignore[arg-type]
        for step in plan_payload.get("steps", [])
    ]
    patch_templates = [
        CreationPatchTemplateModel(**template)  # type: ignore[arg-type]
        for template in plan_payload.get("patch_templates", [])
    ]

    return CreationPlanResponse(
        action=plan_payload.get("action"),
        confidence=float(plan_payload.get("confidence", 0.0)),
        summary=str(plan_payload.get("summary", "")),
        materials=materials,
        steps=steps,
        patch_templates=patch_templates,
        notes=[str(item) for item in plan_payload.get("notes", [])],
        unresolved_tokens=[str(item) for item in plan_payload.get("unresolved_tokens", [])],
        execution_tier=str(plan_payload.get("execution_tier", "needs_confirm")),
        validation_errors=[str(item) for item in plan_payload.get("validation_errors", [])],
        validation_warnings=[str(item) for item in plan_payload.get("validation_warnings", [])],
        missing_fields=[str(item) for item in plan_payload.get("missing_fields", [])],
        unsafe_steps=[str(item) for item in plan_payload.get("unsafe_steps", [])],
        safety_assessment={
            str(key): value
            for key, value in plan_payload.get("safety_assessment", {}).items()
            if isinstance(key, str)
        },
        snapshot_generated_at=plan_result.snapshot_generated_at,
    )


def _sanitize_patch_prefix(player_id: Optional[str]) -> Optional[str]:
    if not player_id:
        return None
    stripped = player_id.strip()
    if not stripped:
        return None
    normalized = "".join(ch.lower() if ch.isalnum() or ch in {"-", "_"} else "-" for ch in stripped)
    normalized = "-".join(filter(None, normalized.split("-")))
    if not normalized:
        return None
    return f"chat-{normalized[:24]}"


@router.post("/execute", response_model=CreationExecuteResponse)
def execute_creation_plan(payload: CreationExecuteRequest) -> CreationExecuteResponse:
    patch_prefix = _sanitize_patch_prefix(payload.player_id)

    try:
        hard_route = creation_workflow.try_creation_hard_route(payload.message, patch_id=patch_prefix)
    except creation_workflow.HardRouteUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if hard_route is not None:
        if payload.dry_run_only:
            raise HTTPException(status_code=400, detail="hard_route_does_not_support_dry_run")

        plan_payload = hard_route.plan_result.plan.to_payload()
        plan_payload["snapshot_generated_at"] = hard_route.plan_result.snapshot_generated_at
        plan_model = CreationPlanResponse(**plan_payload)

        decision_payload = {
            "mode": "creation_hard_route",
            "block_id": hard_route.placement.block_id,
            "coordinates": {
                "x": hard_route.placement.x,
                "y": hard_route.placement.y,
                "z": hard_route.placement.z,
            },
        }

        return CreationExecuteResponse(
            status="ok",
            decision=decision_payload,
            plan=plan_model,
            report=hard_route.report.to_payload(),
        )

    decision = creation_workflow.classify_message(payload.message)
    decision_payload = decision.model_dump()

    if not decision.is_creation:
        return CreationExecuteResponse(status="not_creation", decision=decision_payload)

    plan_result: CreationPlanResult = creation_workflow.generate_plan(decision, message=payload.message)
    plan_payload = plan_result.plan.to_payload()
    plan_payload["snapshot_generated_at"] = plan_result.snapshot_generated_at
    plan_model = CreationPlanResponse(**plan_payload)

    if payload.dry_run_only or not creation_workflow.auto_execute_enabled():
        dry_run_result = creation_workflow.dry_run_plan(plan_result.plan, patch_id=patch_prefix)
        report_payload = {
            "patch_id": dry_run_result.patch_id,
            "dry_run": dry_run_result.to_payload(),
            "execution_results": [],
            "errors": list(dry_run_result.errors),
            "warnings": list(dry_run_result.warnings),
        }
        return CreationExecuteResponse(
            status="dry_run",
            decision=decision_payload,
            plan=plan_model,
            report=report_payload,
        )

    report = creation_workflow.auto_execute_plan(plan_result.plan, patch_id=patch_prefix)
    return CreationExecuteResponse(
        status="ok",
        decision=decision_payload,
        plan=plan_model,
        report=report.to_payload(),
    )
