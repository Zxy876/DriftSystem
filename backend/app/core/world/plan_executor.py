"""Orchestrates dry-run validation followed by automatic world execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Protocol

from app.core.creation.transformer import CreationPlan
from app.core.world.patch_executor import PatchExecutionResult, PatchExecutor
from app.core.world.patch_transaction import PatchTransactionEntry


logger = logging.getLogger(__name__)


class CommandRunner(Protocol):
    """Protocol used to abstract command dispatch (e.g., RCON)."""

    def run(self, commands: Iterable[str]) -> None:
        ...


@dataclass
class TemplateExecutionStatus:
    """Represents the outcome of executing a single template."""

    template_id: str
    step_id: str
    commands: List[str]
    status: str
    transaction: Optional[PatchTransactionEntry]
    error: Optional[str] = None

    def to_payload(self) -> Dict[str, object]:
        return {
            "template_id": self.template_id,
            "step_id": self.step_id,
            "commands": list(self.commands),
            "status": self.status,
            "transaction": {
                "patch_id": self.transaction.patch_id,
                "template_id": self.transaction.template_id,
                "step_id": self.transaction.step_id,
                "status": self.transaction.status,
                "created_at": self.transaction.created_at,
                "metadata": dict(self.transaction.metadata),
            }
            if self.transaction
            else None,
            "error": self.error,
        }


@dataclass
class PlanExecutionReport:
    """Aggregated information after applying a creation plan automatically."""

    patch_id: Optional[str]
    dry_run: PatchExecutionResult
    execution_results: List[TemplateExecutionStatus] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_payload(self) -> Dict[str, object]:
        return {
            "patch_id": self.patch_id,
            "dry_run": self.dry_run.to_payload(),
            "execution_results": [item.to_payload() for item in self.execution_results],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


class PlanExecutor:
    """Apply validated templates to the world using the configured command runner."""

    def __init__(self, patch_executor: PatchExecutor, command_runner: CommandRunner) -> None:
        self._patch_executor = patch_executor
        self._command_runner = command_runner

    def auto_execute(self, plan: CreationPlan, *, patch_id: Optional[str] = None) -> PlanExecutionReport:
        dry_result = self._patch_executor.dry_run(plan, patch_id=patch_id)
        transactions_index = {
            (item.template_id, item.step_id): item for item in dry_result.transactions
        }
        execution_results: List[TemplateExecutionStatus] = []

        for executed in dry_result.executed:
            for command in executed.commands:
                summary = _summarize_setblock(command)
                if summary is not None:
                    x, y, z, block_id = summary
                    logger.info("[PlanExecutor] CREATE_BLOCK → setblock %s %s %s %s", x, y, z, block_id)

        for executed in dry_result.executed:
            entry = transactions_index.get((executed.template_id, executed.step_id))
            if entry is None:
                continue
            try:
                self._command_runner.run(executed.commands)
            except Exception as exc:  # pragma: no cover - re-raised by tests
                updated = self._patch_executor.transaction_log.record_status_update(
                    entry,
                    status="failed",
                    metadata={
                        "mode": "auto_execute",
                        "error": str(exc),
                    },
                )
                execution_results.append(
                    TemplateExecutionStatus(
                        template_id=executed.template_id,
                        step_id=executed.step_id,
                        commands=list(executed.commands),
                        status="failed",
                        transaction=updated,
                        error=str(exc),
                    )
                )
                for command in executed.commands:
                    summary = _summarize_setblock(command)
                    if summary is not None:
                        logger.error("[Drift][FAILED] reason=%s command=%s", exc, command)
            else:
                updated = self._patch_executor.transaction_log.record_status_update(
                    entry,
                    status="pending",
                    metadata={
                        "mode": "auto_execute",
                        "result": "success",
                    },
                )
                execution_results.append(
                    TemplateExecutionStatus(
                        template_id=executed.template_id,
                        step_id=executed.step_id,
                        commands=list(executed.commands),
                        status="pending",
                        transaction=updated,
                    )
                )
                for command in executed.commands:
                    summary = _summarize_setblock(command)
                    if summary is not None:
                        x, y, z, block_id = summary
                        logger.info("[Drift][EXECUTED] setblock %s %s %s %s", x, y, z, block_id)

        report = PlanExecutionReport(
            patch_id=dry_result.patch_id,
            dry_run=dry_result,
            execution_results=execution_results,
            errors=list(dry_result.errors),
            warnings=list(dry_result.warnings),
        )
        for result in execution_results:
            if result.status == "failed" and result.error:
                report.errors.append(result.error)
        return report


def _summarize_setblock(command: str) -> Optional[tuple[str, str, str, str]]:
    if not command:
        return None
    tokens = command.strip().split()
    if len(tokens) < 5:
        return None
    if tokens[0].lower() != "setblock":
        return None
    return tokens[1], tokens[2], tokens[3], tokens[4]