from pathlib import Path

import pytest

from app.core.creation.transformer import CreationPatchTemplate, CreationPlan
from app.core.world.patch_executor import PatchExecutor
from app.core.world.patch_transaction import PatchTransactionLog


@pytest.fixture()
def temp_transaction_log(tmp_path: Path) -> PatchTransactionLog:
    return PatchTransactionLog(root=tmp_path)


def _build_template(
    *,
    step_id: str,
    template_id: str,
    execution_tier: str,
    commands,
    summary: str = "",
    step_type: str = "generic",
):
    template = CreationPatchTemplate(
        step_id=step_id,
        template_id=template_id,
        status="resolved",
        summary=summary or "test template",
        step_type=step_type,
        world_patch={
            "mc": {"commands": commands},
        },
    )
    template.validation.execution_tier = execution_tier
    return template


def test_dry_run_filters_templates_by_execution_tier(temp_transaction_log: PatchTransactionLog) -> None:
    plan = CreationPlan(
        action="build",
        materials=[],
        confidence=0.9,
        summary="Dry run baseline",
        patch_templates=[
            _build_template(
                step_id="safe-1",
                template_id="safe-1",
                execution_tier="safe_auto",
                commands=["setblock 1 2 3 minecraft:stone"],
                summary="Place stone",
                step_type="block_placement",
            ),
            _build_template(
                step_id="needs-confirm",
                template_id="needs-confirm",
                execution_tier="needs_confirm",
                commands=["setblock 4 5 6 minecraft:dirt"],
            ),
            _build_template(
                step_id="unsafe",
                template_id="unsafe",
                execution_tier="safe_auto",
                commands=["say hello"],
            ),
        ],
        notes=[],
        steps=[],
    )

    executor = PatchExecutor(transaction_log=temp_transaction_log)
    result = executor.dry_run(plan, patch_id="test-plan")

    assert [entry.template_id for entry in result.executed] == ["safe-1"]
    assert len(result.transactions) == 1
    assert result.patch_id == "test-plan"
    assert result.transactions[0].status == "validated"

    # Command whitelist rejects say -> command_warnings
    skipped = {entry.template_id: entry.reason for entry in result.skipped}
    assert skipped["needs-confirm"].startswith("execution_tier")
    assert skipped["unsafe"] == "command_warnings"
    assert result.warnings  # say -> warning

    payloads = [entry for entry in temp_transaction_log.load()]

    assert payloads and payloads[0].template_id == "safe-1"
    assert payloads[0].status == "validated"
    assert payloads[0].metadata["mode"] == "dry_run"


def test_dry_run_generates_patch_id_when_missing(temp_transaction_log: PatchTransactionLog) -> None:
    plan = CreationPlan(
        action="build",
        materials=[],
        confidence=0.9,
        summary="Capsule Test",
        patch_templates=[
            _build_template(
                step_id="safe",
                template_id="safe",
                execution_tier="safe_auto",
                commands=["setblock 0 0 0 minecraft:stone"],
            )
        ],
        notes=[],
        steps=[],
    )

    executor = PatchExecutor(transaction_log=temp_transaction_log)
    result = executor.dry_run(plan)

    assert result.transactions
    assert result.patch_id and result.patch_id.startswith("capsule-test")
    assert result.transactions[0].status == "validated"
