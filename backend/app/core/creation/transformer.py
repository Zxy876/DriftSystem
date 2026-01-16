"""Resource \tbehavior transformer for chat-driven creation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

from app.core.intent_creation import CreationIntentDecision
from app.core.world.resource_sanitizer import (
    sanitize_command_list,
    sanitize_resource_location,
    sanitize_world_patch,
)

from .resource_snapshot import ResourceCatalog, ResourceRecord, ResourceSnapshot
from .validation import (
    PatchTemplateValidationResult,
    classify_step_type,
    detect_placeholders,
    validate_patch_template,
)


@dataclass
class CreationPlanMaterial:
    """Material entry produced by the transformer."""

    token: str
    resource_id: Optional[str]
    label: Optional[str]
    status: str
    confidence: float
    quantity: int
    tags: List[str] = field(default_factory=list)

    def to_payload(self) -> Dict[str, object]:
        return {
            "token": self.token,
            "resource_id": self.resource_id,
            "label": self.label,
            "status": self.status,
            "confidence": round(self.confidence, 3),
            "quantity": self.quantity,
            "tags": list(self.tags),
        }


@dataclass
class CreationPatchTemplate:
    """Draft world_patch template derived from a plan step."""

    step_id: str
    template_id: str
    status: str
    summary: str
    step_type: str
    world_patch: Dict[str, object] = field(default_factory=dict)
    mod_hooks: List[str] = field(default_factory=list)
    requires_player_pose: bool = False
    notes: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    validation: PatchTemplateValidationResult = field(
        default_factory=lambda: PatchTemplateValidationResult(
            errors=[],
            warnings=[],
            execution_tier="needs_confirm",
            missing_fields=[],
            unsafe_placeholders=[],
        )
    )

    def to_payload(self) -> Dict[str, object]:
        sanitized_world_patch = sanitize_world_patch(self.world_patch, context=self.step_id)
        return {
            "step_id": self.step_id,
            "template_id": self.template_id,
            "status": self.status,
            "summary": self.summary,
            "step_type": self.step_type,
            "world_patch": sanitized_world_patch,
            "mod_hooks": list(self.mod_hooks),
            "requires_player_pose": self.requires_player_pose,
            "notes": list(self.notes),
            "tags": list(self.tags),
            "validation": self.validation.to_payload(),
        }


@dataclass
class CreationPlan:
    """Structured plan describing the intended creation."""

    action: Optional[str]
    materials: List[CreationPlanMaterial]
    confidence: float
    summary: str
    steps: List["CreationPlanStep"] = field(default_factory=list)
    patch_templates: List[CreationPatchTemplate] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    execution_tier: str = "needs_confirm"
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    unsafe_steps: List[str] = field(default_factory=list)
    safety_assessment: Dict[str, object] = field(default_factory=dict)

    def unresolved_tokens(self) -> List[str]:
        return [material.token for material in self.materials if material.status != "resolved"]

    def to_payload(self) -> Dict[str, object]:
        return {
            "action": self.action,
            "confidence": round(self.confidence, 3),
            "summary": self.summary,
            "materials": [material.to_payload() for material in self.materials],
            "steps": [step.to_payload() for step in self.steps],
            "patch_templates": [template.to_payload() for template in self.patch_templates],
            "notes": list(self.notes),
            "unresolved_tokens": self.unresolved_tokens(),
            "execution_tier": self.execution_tier,
            "validation_errors": list(self.validation_errors),
            "validation_warnings": list(self.validation_warnings),
            "missing_fields": list(self.missing_fields),
            "unsafe_steps": list(self.unsafe_steps),
            "safety_assessment": dict(self.safety_assessment),
        }


@dataclass
class CreationPlanResult:
    """Wrapper containing plan details alongside the snapshot metadata."""

    plan: CreationPlan
    snapshot_generated_at: Optional[str]

    def to_payload(self) -> Dict[str, object]:
        payload = self.plan.to_payload()
        payload["snapshot_generated_at"] = self.snapshot_generated_at
        return payload


@dataclass
class CreationPlanStep:
    """Draft step describing how to apply a resource in the world."""

    step_id: str
    title: str
    description: str
    status: str
    step_type: str = "manual_review"
    commands: List[str] = field(default_factory=list)
    required_resource: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_payload(self) -> Dict[str, object]:
        sanitized_commands, step_changes = sanitize_command_list(self.commands, context=self.step_id)
        if step_changes:
            logger.warning(
                "step_commands_sanitized[%s]: %s",
                self.step_id,
                "; ".join(step_changes),
            )
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "step_type": self.step_type,
            "commands": sanitized_commands,
            "required_resource": self.required_resource,
            "tags": list(self.tags),
        }


logger = logging.getLogger(__name__)


class CreationTransformer:
    """Derive a rough creation plan from intent classifier output."""

    def __init__(self, catalog: Optional[ResourceCatalog] = None) -> None:
        self._catalog = catalog or ResourceCatalog()

    def transform(
        self,
        decision: CreationIntentDecision,
        *,
        snapshot: Optional[ResourceSnapshot] = None,
        default_quantity: int = 12,
    ) -> CreationPlanResult:
        if snapshot is None:
            snapshot = self._catalog.load_snapshot()

        action = self._select_action(decision.slots.get("actions", []))
        material_tokens = [token for token in decision.slots.get("materials", []) if token]
        materials: List[CreationPlanMaterial] = []
        resource_lookup: Dict[str, ResourceRecord] = {}

        for token in material_tokens:
            candidates = snapshot.find_candidates(token)
            if not candidates:
                materials.append(
                    CreationPlanMaterial(
                        token=token,
                        resource_id=None,
                        label=None,
                        status="unresolved",
                        confidence=0.0,
                        quantity=0,
                    )
                )
                continue
            record, score = candidates[0]
            sanitized_resource_id = sanitize_resource_location(
                record.resource_id,
                context="catalog_record",
            )
            if sanitized_resource_id and sanitized_resource_id != record.resource_id:
                logger.warning(
                    "resource_id_normalised token=%s original=%s sanitised=%s",
                    token,
                    record.resource_id,
                    sanitized_resource_id,
                )
                record.resource_id = sanitized_resource_id
            quantity = self._estimate_quantity(record, default_quantity)
            materials.append(
                CreationPlanMaterial(
                    token=token,
                    resource_id=record.resource_id,
                    label=record.label,
                    status="resolved",
                    confidence=score,
                    quantity=quantity,
                    tags=list(record.tags),
                )
            )
            resource_lookup[record.resource_id] = record

        resolved = [material for material in materials if material.status == "resolved"]
        resolution_ratio = (len(resolved) / len(materials)) if materials else 0.0
        plan_confidence = self._plan_confidence(decision.confidence, resolution_ratio)
        summary = self._build_summary(action, resolved, materials)
        notes = self._generate_notes(decision, materials)
        plan_action = action or "create"
        steps = self._build_steps(plan_action, materials, resource_lookup)
        patch_templates = self._build_patch_templates(materials, steps, resource_lookup)

        tier_order = {"safe_auto": 0, "needs_confirm": 1, "blocked": 2}
        plan_execution_tier = "safe_auto"
        validation_errors: List[str] = []
        validation_warnings: List[str] = []
        missing_fields: List[str] = []
        unsafe_steps: List[str] = []

        for template in patch_templates:
            template_payload = {
                "step_id": template.step_id,
                "template_id": template.template_id,
                "status": template.status,
                "summary": template.summary,
                "step_type": template.step_type,
                "world_patch": template.world_patch,
                "mod_hooks": template.mod_hooks,
            }
            validation = validate_patch_template(template_payload)
            template.validation = validation
            validation_errors.extend(validation.errors)
            validation_warnings.extend(validation.warnings)
            missing_fields.extend(validation.missing_fields)
            if validation.execution_tier != "safe_auto":
                unsafe_steps.append(template.step_id)
            if tier_order.get(validation.execution_tier, 1) > tier_order.get(plan_execution_tier, 0):
                plan_execution_tier = validation.execution_tier

        for step in steps:
            if step.status != "resolved" and step.step_id not in unsafe_steps:
                unsafe_steps.append(step.step_id)

        unresolved_tokens = [material.token for material in materials if material.status != "resolved"]
        missing_fields.extend(f"material:{token}" for token in unresolved_tokens)

        safety_assessment = {
            "world_damage_risk": "low"
            if plan_execution_tier == "safe_auto"
            else ("medium" if plan_execution_tier == "needs_confirm" else "high"),
            "reversibility": plan_execution_tier != "blocked",
            "requires_confirmation": plan_execution_tier != "safe_auto",
        }

        plan = CreationPlan(
            action=plan_action,
            materials=materials,
            confidence=plan_confidence,
            summary=summary,
            steps=steps,
            patch_templates=patch_templates,
            notes=notes,
            execution_tier=plan_execution_tier,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            missing_fields=missing_fields,
            unsafe_steps=unsafe_steps,
            safety_assessment=safety_assessment,
        )
        return CreationPlanResult(plan=plan, snapshot_generated_at=snapshot.generated_at)

    @staticmethod
    def _select_action(actions: Iterable[str]) -> Optional[str]:
        for action in actions:
            token = str(action).strip()
            if token:
                return token
        return None

    @staticmethod
    def _estimate_quantity(record: ResourceRecord, fallback: int) -> int:
        if record.available and record.available > 0:
            return min(record.available, max(fallback, 4))
        return fallback

    @staticmethod
    def _plan_confidence(intent_confidence: float, resolution_ratio: float) -> float:
        base = max(intent_confidence, 0.3)
        combined = base * 0.6 + resolution_ratio * 0.4
        return round(min(max(combined, 0.0), 1.0), 3)

    @staticmethod
    def _build_summary(
        action: Optional[str],
        resolved_materials: List[CreationPlanMaterial],
        all_materials: List[CreationPlanMaterial],
    ) -> str:
        action_text = action or "create"
        if resolved_materials:
            labels = ", ".join(material.label or material.token for material in resolved_materials)
            return f"{action_text} with {labels}"
        if all_materials:
            tokens = ", ".join(material.token for material in all_materials)
            return f"{action_text} using {tokens} (pending mapping)"
        return f"{action_text} (no materials detected)"

    @staticmethod
    def _generate_notes(decision: CreationIntentDecision, materials: List[CreationPlanMaterial]) -> List[str]:
        notes: List[str] = []
        if not decision.is_creation:
            notes.append("意图分类为非创造，Transformer 结果仅供参考。")
        unresolved = [material.token for material in materials if material.status != "resolved"]
        if unresolved:
            unresolved_str = ", ".join(unresolved)
            notes.append(f"未能匹配资源：{unresolved_str}")
        return notes

    @staticmethod
    def _build_steps(
        action: str,
        materials: List[CreationPlanMaterial],
        resource_lookup: Dict[str, ResourceRecord],
    ) -> List[CreationPlanStep]:
        steps: List[CreationPlanStep] = []
        for idx, material in enumerate(materials, start=1):
            step_id = f"step-{idx}"
            if material.status != "resolved":
                steps.append(
                    CreationPlanStep(
                        step_id=step_id,
                        title=f"待确认：{material.token}",
                        description=f"未能匹配资源“{material.token}”，请与玩家确认具体方块或结构后再生成 patch。",
                        status="needs_review",
                        step_type="manual_review",
                    )
                )
                continue
            record = resource_lookup.get(material.resource_id or "")
            commands = record.commands[:3] if record else []
            tags = list(record.tags) if record else []
            description = f"使用 {material.label or material.token} 完成 {action} 场景的布置。"
            status = "resolved" if commands else "draft"
            if not commands:
                description += "（无现成指令，可参考 patch 模板或手动编排 setblock 序列。）"
            step_type = classify_step_type(commands, status)
            if step_type == "custom_command" and status == "resolved":
                status = "draft"
            steps.append(
                CreationPlanStep(
                    step_id=step_id,
                    title=f"部署 {material.label or material.token}",
                    description=description,
                    status=status,
                    step_type=step_type,
                    commands=commands,
                    required_resource=material.resource_id,
                    tags=tags,
                )
            )
        if not steps:
            steps.append(
                CreationPlanStep(
                    step_id="step-1",
                    title="澄清创造需求",
                    description="未检索到可执行材料，请与玩家确认建造细节后重新生成计划。",
                    status="needs_review",
                    step_type="manual_review",
                )
            )
        return steps

    def _build_patch_templates(
        self,
        materials: List[CreationPlanMaterial],
        steps: List[CreationPlanStep],
        resource_lookup: Dict[str, ResourceRecord],
    ) -> List[CreationPatchTemplate]:
        templates: List[CreationPatchTemplate] = []
        material_by_resource = {
            material.resource_id: material
            for material in materials
            if material.resource_id
        }
        for step in steps:
            resource_id_raw = step.required_resource or ""
            resource_id = sanitize_resource_location(resource_id_raw, context=f"step:{step.step_id}") if resource_id_raw else ""
            material = material_by_resource.get(resource_id)
            record = resource_lookup.get(resource_id)
            commands = list(step.commands)
            if commands:
                commands, _ = sanitize_command_list(commands, context=step.step_id)
            placeholders = detect_placeholders(commands)
            tags: Set[str] = set(step.tags)
            if record:
                tags.update(record.tags)
            mod_hooks = sorted(
                tag.split(":", 1)[1]
                for tag in tags
                if tag.startswith("mod:") and len(tag.split(":", 1)[1]) > 0
            )
            tags_list = sorted(tags)
            requires_pose = bool(placeholders)
            notes: List[str] = []
            if step.status == "needs_review":
                notes.append("资源未确认，需手动选择 world_patch 模板。")
            if not commands:
                notes.append("无预设命令，请手动编排 setblock/fill 序列。")
            if placeholders:
                placeholders_str = ", ".join(sorted(placeholders))
                notes.append(f"命令包含占位符：{placeholders_str}。")
            metadata: Dict[str, object] = {}
            if resource_id:
                metadata["resource_id"] = resource_id
            if material:
                metadata["material"] = {
                    "token": material.token,
                    "label": material.label,
                    "quantity": material.quantity,
                }
            if step.description:
                metadata["step_description"] = step.description
            if tags_list:
                metadata["tags"] = tags_list
            if placeholders:
                metadata["placeholders"] = sorted(placeholders)
            if requires_pose:
                metadata.setdefault("requirements", []).append("player_pose")
            world_patch: Dict[str, object] = {}
            if commands:
                world_patch["mc"] = {"commands": commands}
            if metadata:
                world_patch["metadata"] = metadata
            template_id = f"{resource_id or step.step_id}::default" if resource_id else f"{step.step_id}::manual"
            templates.append(
                CreationPatchTemplate(
                    step_id=step.step_id,
                    template_id=template_id,
                    status=step.status,
                    summary=step.title,
                    step_type=step.step_type,
                    world_patch=world_patch,
                    mod_hooks=mod_hooks,
                    requires_player_pose=requires_pose,
                    notes=notes,
                    tags=tags_list,
                )
            )
        return templates

    @property
    def catalog(self) -> ResourceCatalog:
        return self._catalog


def load_default_transformer() -> CreationTransformer:
    return CreationTransformer()
