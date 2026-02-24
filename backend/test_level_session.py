"""LevelSession 状态机测试。

模块角色：验证四阶段状态机的合法流转与持久化。
不做什么：不触发真实布景/彩排逻辑，仅测试 sqlite 状态记录。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.levels.level_session import ALLOWED_TRANSITIONS, LevelSessionStore, STAGES


@pytest.fixture()
def store(tmp_path: Path) -> LevelSessionStore:
    db_path = tmp_path / "sessions.db"
    return LevelSessionStore(db_path)


def test_create_and_get_state(store: LevelSessionStore) -> None:
    store.create_session("level_a")
    assert store.get_state("level_a") == "IMPORTED"


def test_valid_flow(store: LevelSessionStore) -> None:
    level_id = "level_b"
    store.create_session(level_id)
    for current, target in ALLOWED_TRANSITIONS.items():
        assert store.get_state(level_id) == current
        store.advance(level_id, target_state=target, actor_id="director")
    assert store.get_state(level_id) == "TAKE"


def test_disallow_jump(store: LevelSessionStore) -> None:
    level_id = "level_c"
    store.create_session(level_id)
    with pytest.raises(ValueError):
        store.advance(level_id, target_state="REHEARSE")


def test_unknown_level_raises(store: LevelSessionStore) -> None:
    with pytest.raises(ValueError):
        store.advance("unknown", target_state="SET_DRESS")


def test_persistence_across_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    first = LevelSessionStore(db_path)
    first.create_session("level_d")
    first.advance("level_d", target_state="SET_DRESS", actor_id="director")

    # reopen
    second = LevelSessionStore(db_path)
    assert second.get_state("level_d") == "SET_DRESS"


def test_invalid_state_name(store: LevelSessionStore) -> None:
    store.create_session("level_e")
    with pytest.raises(ValueError):
        store.advance("level_e", target_state="UNKNOWN")


def test_recreate_session_no_side_effect(store: LevelSessionStore) -> None:
    store.create_session("level_f")
    store.advance("level_f", target_state="SET_DRESS")
    # 再次创建不会重置状态
    store.create_session("level_f")
    assert store.get_state("level_f") == "SET_DRESS"
