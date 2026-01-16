from pathlib import Path
from typing import Iterable, List

import pytest

from app.core.creation.transformer import CreationPatchTemplate, CreationPlan
from app.core.world.plan_executor import PlanExecutor, PlanExecutionReport
from app.core.world.patch_executor import PatchExecutor
from app.core.world.patch_transaction import PatchTransactionLog
from app.services import creation_workflow


@pytest.fixture()
def temp_transaction_log(tmp_path: Path) -> PatchTransactionLog:
    return PatchTransactionLog(root=tmp_path)


def _build_template(
    *,
    template_id: str,
    commands: List[str],
    step_id: str = "step-1",
):
    template = CreationPatchTemplate(
        step_id=step_id,
        template_id=template_id,
        status="resolved",
        summary="test",
        step_type="block_placement",
        world_patch={"mc": {"commands": commands}},
    )
    template.validation.execution_tier = "safe_auto"
    return template


class FakeRunner:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.dispatched: List[List[str]] = []

    def run(self, commands: Iterable[str]) -> None:
        payload = [cmd for cmd in commands]
        if self.should_fail:
            raise RuntimeError("dispatch failed")
        self.dispatched.append(payload)


def _build_plan(template: CreationPatchTemplate) -> CreationPlan:
    return CreationPlan(
        action="build",
        materials=[],
        confidence=0.9,
        summary="Auto execute plan",
        patch_templates=[template],
        notes=[],
        steps=[],
    )


def test_plan_executor_runs_commands_and_marks_pending(temp_transaction_log: PatchTransactionLog) -> None:
    template = _build_template(template_id="safe", commands=["setblock 1 2 3 minecraft:stone"])
    plan = _build_plan(template)

    runner = FakeRunner()
    executor = PlanExecutor(PatchExecutor(transaction_log=temp_transaction_log), runner)
    report = executor.auto_execute(plan, patch_id="auto-test")

    assert runner.dispatched == [["setblock 1 2 3 minecraft:stone"]]
    assert report.patch_id == "auto-test"
    assert report.execution_results and report.execution_results[0].status == "pending"

    entries = temp_transaction_log.load()
    statuses = [entry.status for entry in entries]
    assert statuses == ["validated", "pending"]


def test_plan_executor_records_failure(temp_transaction_log: PatchTransactionLog) -> None:
    template = _build_template(template_id="broken", commands=["setblock 0 0 0 minecraft:dirt"])
    plan = _build_plan(template)

    runner = FakeRunner(should_fail=True)
    executor = PlanExecutor(PatchExecutor(transaction_log=temp_transaction_log), runner)
    report = executor.auto_execute(plan)

    assert report.execution_results and report.execution_results[0].status == "failed"
    assert "dispatch failed" in (report.execution_results[0].error or "")
    assert any("dispatch failed" in err for err in report.errors)

    entries = temp_transaction_log.load()
    statuses = [entry.status for entry in entries]
    assert statuses == ["validated", "failed"]


def test_world_patch_from_report_auto_execute(temp_transaction_log: PatchTransactionLog) -> None:
    template = _build_template(template_id="auto", commands=["setblock 1 1 1 minecraft:gold_block"])
    plan = _build_plan(template)

    runner = FakeRunner()
    executor = PlanExecutor(PatchExecutor(transaction_log=temp_transaction_log), runner)
    report = executor.auto_execute(plan, patch_id="world-patch-auto")

    world_patch = creation_workflow.world_patch_from_report(report)
    assert world_patch is not None
    assert world_patch["mc"]["commands"] == ["setblock 1 1 1 minecraft:gold_block"]
    metadata = world_patch["metadata"]
    assert metadata["mode"] == "auto_execute"
    assert metadata["patch_id"] == "world-patch-auto"
    assert metadata["templates"][0]["status"] == "pending"


def test_world_patch_from_report_dry_run_only(temp_transaction_log: PatchTransactionLog) -> None:
    template = _build_template(template_id="dry", commands=["setblock 2 2 2 minecraft:stone"])
    plan = _build_plan(template)

    patch_executor = PatchExecutor(transaction_log=temp_transaction_log)
    dry_run = patch_executor.dry_run(plan, patch_id="world-patch-dry")
    report = PlanExecutionReport(
        patch_id=dry_run.patch_id,
        dry_run=dry_run,
        execution_results=[],
        errors=list(dry_run.errors),
        warnings=list(dry_run.warnings),
    )

    world_patch = creation_workflow.world_patch_from_report(report)
    assert world_patch is not None
    assert world_patch["metadata"]["mode"] == "dry_run"
    assert world_patch["metadata"]["templates"][0]["status"] == "validated"