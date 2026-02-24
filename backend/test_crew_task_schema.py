"""Tests for Crew Task schema (Issue 3.1)."""
from pathlib import Path

import json

import pytest
from pydantic import ValidationError

from app.schemas.crew_task import CrewTask, load_crew_task


def test_load_example_json(tmp_path: Path) -> None:
    src = Path(__file__).parent.parent / "docs" / "v1.21" / "crew_task_example.json"
    task = load_crew_task(src)
    assert task.task_id == "crew-task-001"
    assert len(task.actions) == 3
    assert task.actions[0].action == "setblock"


def test_reject_invalid_action() -> None:
    data = {
        "task_id": "bad-action",
        "level_id": "level-alpha",
        "assigned_to": "crew-team-a",
        "summary": "invalid action",
        "actions": [
            {
                "action": "fly",
                "position": [0, 0, 0],
            }
        ],
    }
    with pytest.raises(ValidationError):
        CrewTask.model_validate(data)


def test_require_fields_per_action() -> None:
    missing_block = {
        "task_id": "no-block",
        "level_id": "level-alpha",
        "assigned_to": "crew-team-a",
        "summary": "missing block",
        "actions": [
            {"action": "setblock", "position": [0, 0, 0]},
        ],
    }
    with pytest.raises(ValidationError):
        CrewTask.model_validate(missing_block)

    missing_region = {
        "task_id": "no-region",
        "level_id": "level-alpha",
        "assigned_to": "crew-team-a",
        "summary": "missing region",
        "actions": [
            {"action": "clear"},
        ],
    }
    with pytest.raises(ValidationError):
        CrewTask.model_validate(missing_region)

    missing_position = {
        "task_id": "no-position",
        "level_id": "level-alpha",
        "assigned_to": "crew-team-a",
        "summary": "missing position",
        "actions": [
            {"action": "travel"},
        ],
    }
    with pytest.raises(ValidationError):
        CrewTask.model_validate(missing_position)


def test_position_and_region_lengths() -> None:
    bad_position = {
        "task_id": "bad-pos",
        "level_id": "level-alpha",
        "assigned_to": "crew-team-a",
        "summary": "bad position",
        "actions": [
            {"action": "travel", "position": [1, 2]},
        ],
    }
    with pytest.raises(ValidationError):
        CrewTask.model_validate(bad_position)

    bad_region = {
        "task_id": "bad-region",
        "level_id": "level-alpha",
        "assigned_to": "crew-team-a",
        "summary": "bad region",
        "actions": [
            {"action": "clear", "region": [1, 2, 3]},
        ],
    }
    with pytest.raises(ValidationError):
        CrewTask.model_validate(bad_region)