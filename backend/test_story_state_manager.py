import os
from pathlib import Path

import pytest

from app.core.ideal_city.story_state import StoryState
from app.core.ideal_city.story_state_manager import StoryStateManager
from app.core.ideal_city.story_state_repository import StoryStateRepository


@pytest.fixture()
def story_repo(tmp_path: Path) -> StoryStateRepository:
    return StoryStateRepository(tmp_path / "story_state")


def test_sync_execution_feedback_completed(story_repo: StoryStateRepository) -> None:
    manager = StoryStateManager(story_repo)
    state = StoryState(player_id="player", scenario_id="default", ready_for_build=True)
    story_repo.save(state)

    updated = manager.sync_execution_feedback(
        player_id="player",
        scenario_id="default",
        plan_id="plan123",
        status="completed",
        command_count=3,
        summary="夜间展台部署",
        log_path=os.path.join("/tmp", "plan123.json"),
    )

    assert updated.ready_for_build is False
    assert updated.last_plan_id == "plan123"
    assert updated.last_plan_status == "completed"
    assert any("建造完成" in note for note in updated.notes)

    refreshed = manager.sync_execution_feedback(
        player_id="player",
        scenario_id="default",
        plan_id="plan123",
        status="completed",
        command_count=3,
        summary="夜间展台部署",
    )

    assert len(refreshed.notes) == len(updated.notes)


def test_sync_execution_feedback_blocked(story_repo: StoryStateRepository) -> None:
    manager = StoryStateManager(story_repo)
    state = StoryState(player_id="player", scenario_id="blocked", ready_for_build=True)
    story_repo.save(state)

    updated = manager.sync_execution_feedback(
        player_id="player",
        scenario_id="blocked",
        plan_id="plan456",
        status="blocked",
        command_count=0,
        missing_mods=["gm4:balloon_animals"],
        summary="夜景布置",
    )

    assert updated.ready_for_build is False
    assert "缺少模组" in " ".join(updated.blocking)
    assert any("受阻" in note for note in updated.notes)
