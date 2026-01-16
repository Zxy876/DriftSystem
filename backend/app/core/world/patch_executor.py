"""Patch execution routines supporting Phase 3 dry-run workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from app.core.creation.transformer import CreationPatchTemplate, CreationPlan
from app.core.creation.validation import validate_patch_template
from app.core.world.command_safety import analyze_commands
from app.core.world.patch_transaction import PatchTransactionEntry, PatchTransactionLog


@dataclass
class DryRunExecutedTemplate:
    """Represents a template that is ready for execution during a dry run."""

    step_id: str
    template_id: str
    commands: List[str]
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, object]:
        return {
            "step_id": self.step_id,
            "template_id": self.template_id,
            "commands": list(self.commands),
            "metadata": dict(self.metadata),
        }


@dataclass
class DryRunSkippedTemplate:
    """Captures the reason why a template was skipped during dry run."""

    step_id: str
    template_id: str
    reason: str

    def to_payload(self) -> Dict[str, object]:
        return {
            "step_id": self.step_id,
            "template_id": self.template_id,
            "reason": self.reason,
        }


@dataclass
class PatchExecutionResult:
    """Aggregated outcome returned by :meth:`PatchExecutor.dry_run`."""

    executed: List[DryRunExecutedTemplate] = field(default_factory=list)
    skipped: List[DryRunSkippedTemplate] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    transactions: List[PatchTransactionEntry] = field(default_factory=list)
    patch_id: Optional[str] = None

    def to_payload(self) -> Dict[str, object]:
        return {
            "executed": [entry.to_payload() for entry in self.executed],
            "skipped": [entry.to_payload() for entry in self.skipped],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "transactions": [
                {
                    "patch_id": item.patch_id,
                    "template_id": item.template_id,
                    "step_id": item.step_id,
                    "status": item.status,
                    "created_at": item.created_at,
                    "metadata": dict(item.metadata),
                }
                for item in self.transactions
            ],
            "patch_id": self.patch_id,
        }


class PatchExecutor:
    """Handles validation and logging for patch execution workflows."""

    def __init__(self, transaction_log: Optional[PatchTransactionLog] = None) -> None:
        self._log = transaction_log or PatchTransactionLog()

    @property
    def transaction_log(self) -> PatchTransactionLog:
        return self._log

    def dry_run(self, plan: CreationPlan, *, patch_id: Optional[str] = None) -> PatchExecutionResult:
        """Evaluate a creation plan without dispatching commands.

        Templates must pass the Phase 3 safety contract (`execution_tier == safe_auto`),
        include explicit command lists, and satisfy the command whitelist. Qualifying
        templates are recorded in the transaction log with ``status=pending`` so they can
        later be replayed by the real executor.
        """

        if not isinstance(plan, CreationPlan):
            raise TypeError("plan must be a CreationPlan instance")

        result = PatchExecutionResult()
        effective_patch_id = patch_id or self._generate_patch_id(plan)

        for template in plan.patch_templates:
            validation = getattr(template, "validation", None)
            if validation is None or not getattr(validation, "execution_tier", None):
                validation = validate_patch_template(template.to_payload())
            execution_tier = getattr(validation, "execution_tier", "needs_confirm")

            if execution_tier != "safe_auto":
                result.skipped.append(
                    DryRunSkippedTemplate(
                        step_id=template.step_id,
                        template_id=template.template_id,
                        reason=f"execution_tier:{execution_tier}",
                    )
                )
                continue

            commands = _extract_commands(template)
            if not commands:
                result.skipped.append(
                    DryRunSkippedTemplate(
                        step_id=template.step_id,
                        template_id=template.template_id,
                        reason="no_commands",
                    )
                )
                continue

            report = analyze_commands(commands)
            if report.errors:
                result.errors.extend(report.errors)
                result.skipped.append(
                    DryRunSkippedTemplate(
                        step_id=template.step_id,
                        template_id=template.template_id,
                        reason="command_errors",
                    )
                )
                continue
            if report.warnings:
                result.warnings.extend(report.warnings)
                result.skipped.append(
                    DryRunSkippedTemplate(
                        step_id=template.step_id,
                        template_id=template.template_id,
                        reason="command_warnings",
                    )
                )
                continue

            metadata = _extract_metadata(template)
            executed_entry = DryRunExecutedTemplate(
                step_id=template.step_id,
                template_id=template.template_id,
                commands=commands,
                metadata=metadata,
            )
            result.executed.append(executed_entry)

            transaction = self._log.record(
                patch_id=effective_patch_id,
                template_id=template.template_id,
                step_id=template.step_id,
                commands=commands,
                undo_patch=_extract_undo_patch(template),
                status="validated",
                metadata={
                    "mode": "dry_run",
                    "summary": template.summary,
                    "step_type": template.step_type,
                    "tags": list(getattr(template, "tags", [])),
                    "plan_summary": plan.summary,
                    "plan_execution_tier": plan.execution_tier,
                },
            )
            result.transactions.append(transaction)

        result.patch_id = effective_patch_id
        return result

    def _generate_patch_id(self, plan: CreationPlan) -> str:
        base = plan.summary or plan.action or "creation-plan"
        sanitized = "".join(ch.lower() if ch.isalnum() else "-" for ch in base)
        sanitized = "-".join(filter(None, sanitized.split("-")))
        if not sanitized:
            sanitized = "creation-plan"
        return f"{sanitized[:32]}-{uuid4().hex[:8]}"


def _extract_commands(template: CreationPatchTemplate) -> List[str]:
    mc_section = template.world_patch.get("mc") if isinstance(template.world_patch, dict) else None
    commands: Iterable[str]
    if isinstance(mc_section, dict):
        commands = mc_section.get("commands") or []
    else:
        commands = []
    return [cmd for cmd in commands if isinstance(cmd, str) and cmd.strip()]


def _extract_metadata(template: CreationPatchTemplate) -> Dict[str, object]:
    metadata = template.world_patch.get("metadata") if isinstance(template.world_patch, dict) else {}
    if not isinstance(metadata, dict):
        return {}
    return dict(metadata)


def _extract_undo_patch(template: CreationPatchTemplate) -> Dict[str, object]:
    undo_patch = template.world_patch.get("undo_patch") if isinstance(template.world_patch, dict) else None
    if isinstance(undo_patch, dict):
        return dict(undo_patch)
    return {"commands": []}
