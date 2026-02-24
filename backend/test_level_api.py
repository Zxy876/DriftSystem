"""Level transition API 测试。

模块角色：验证 /levels/{id}/transition 路由的权限与状态流转。
不做什么：不测试真实布景/彩排，只校验状态机调用与 403/400 分支。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.level_api import LEVEL_SESSION_DB, router as level_router


@pytest.fixture(autouse=True)
def _reset_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRIFT_LEVEL_SESSION_DB", str(tmp_path / "sessions.db"))
    monkeypatch.setenv("DRIFT_DIRECTOR_TOKEN", "secret-token")
    # 清理默认常量以确保使用 env 路径
    if LEVEL_SESSION_DB.exists():
        LEVEL_SESSION_DB.unlink()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(level_router)
    return TestClient(app)


def test_transition_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    resp = client.post(
        "/levels/scene_001/transition",
        params={"target_state": "SET_DRESS"},
        headers={"X-Director-Token": "secret-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "SET_DRESS"


def test_transition_requires_director_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    resp = client.post(
        "/levels/scene_002/transition",
        params={"target_state": "SET_DRESS"},
    )
    assert resp.status_code == 403


def test_transition_invalid_jump(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    # create session implicitly, then try illegal jump
    resp = client.post(
        "/levels/scene_003/transition",
        params={"target_state": "REHEARSE"},
        headers={"X-Director-Token": "secret-token"},
    )
    assert resp.status_code == 400