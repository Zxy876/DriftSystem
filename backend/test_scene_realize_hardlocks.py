from __future__ import annotations

from importlib import reload

from fastapi.testclient import TestClient


def _setup_client() -> TestClient:
    import app.routers.scene as scene_router
    import app.main as app_main

    reload(scene_router)
    reload(app_main)
    return TestClient(app_main.app)


def test_scene_realize_blocks_text_and_narrative(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    client = _setup_client()

    response = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_1",
            "player_id": "p1",
            "mode": "personal",
            "domain": "P1",
            "anchor": {"x": 1000, "y": 64, "z": 0},
            "assets": [{"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 1000, "y": 64, "z": 0}}],
            "text": "请帮我直接建造",
            "narrative": {"text": ["不要进入建造链路"]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert "text_input_forbidden" in body["errors"]
    assert "narrative_input_forbidden" in body["errors"]


def test_scene_realize_needs_review_has_no_plan_or_patch(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    client = _setup_client()

    response = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_2",
            "player_id": "p1",
            "mode": "personal",
            "domain": "P1",
            "anchor": {"x": 1000, "y": 64, "z": 0},
            "assets": [{"resource_id": "drift:not_exists", "anchor": {"x": 1000, "y": 64, "z": 0}}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_review"
    assert body["plan_id"] is None
    assert body["patch_id"] is None
    assert body["selected_assets"] == []
    assert body["needs_review"]


def test_scene_realize_ok_status_is_in_fixed_set(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    client = _setup_client()

    response = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_3",
            "player_id": "p1",
            "mode": "personal",
            "domain": "P1",
            "anchor": {"x": 1000, "y": 64, "z": 0},
            "assets": [{"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 1000, "y": 64, "z": 0}}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "needs_review", "blocked"}
    assert body["status"] == "ok"
    assert body["execution_mode"] == "dry_run"
    assert body["execution"]["mode"] == "dry_run"
    assert body["plan_id"] is not None
    assert body["patch_id"] is not None
    assert body["mode"] == "personal"
    assert body["domain"] == "P1"


def test_mode_domain_binding_shared_forces_S(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    client = _setup_client()

    response = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_4",
            "player_id": "shared_player",
            "mode": "shared",
            "domain": "P9",
            "anchor": {"x": 0, "y": 64, "z": 0},
            "assets": [{"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 0, "y": 64, "z": 0}}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["domain"] == "S"
    assert body["domain_candidate"] == "P9"
    assert body["domain_overridden"] is True


def test_player_domain_mapping_is_server_owned(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    client = _setup_client()

    first = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_5_a",
            "player_id": "alice",
            "mode": "personal",
            "domain": "P99",
            "anchor": {"x": 1000, "y": 64, "z": 0},
            "assets": [{"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 1000, "y": 64, "z": 0}}],
        },
    )
    second = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_5_b",
            "player_id": "alice",
            "mode": "personal",
            "domain": "S",
            "anchor": {"x": 1000, "y": 64, "z": 10},
            "assets": [{"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 1000, "y": 64, "z": 10}}],
        },
    )
    third = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_5_c",
            "player_id": "bob",
            "mode": "personal",
            "domain": "P1",
            "anchor": {"x": 2000, "y": 64, "z": 0},
            "assets": [{"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 2000, "y": 64, "z": 0}}],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    body_a = first.json()
    body_b = second.json()
    body_c = third.json()
    assert body_a["domain"] == "P1"
    assert body_b["domain"] == "P1"
    assert body_c["domain"] == "P2"


def test_out_of_domain_asset_is_blocked_with_no_plan(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    client = _setup_client()

    response = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_6",
            "player_id": "p1",
            "mode": "personal",
            "domain": "P1",
            "anchor": {"x": 1000, "y": 64, "z": 0},
            "assets": [{"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 0, "y": 64, "z": 0}}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["plan_id"] is None
    assert body["patch_id"] is None
    assert any(error.endswith("out_of_domain") for error in body["errors"])


def test_execute_mode_blocked_when_server_gate_off(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    monkeypatch.delenv("DRIFT_SCENE_REALIZE_ALLOW_EXECUTE", raising=False)
    client = _setup_client()

    response = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_7",
            "player_id": "p1",
            "mode": "personal",
            "domain": "P1",
            "execution_mode": "execute",
            "anchor": {"x": 1000, "y": 64, "z": 0},
            "assets": [{"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 1000, "y": 64, "z": 0}}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["plan_id"] is None
    assert body["patch_id"] is None
    assert "execute_mode_not_enabled" in body["errors"]


def test_execute_mode_ok_when_gate_on_and_runtime_available(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    monkeypatch.setenv("DRIFT_SCENE_REALIZE_ALLOW_EXECUTE", "1")

    class _FakeReport:
        def to_payload(self):
            return {
                "patch_id": "fake-patch",
                "dry_run": {"executed": [], "skipped": [], "errors": [], "warnings": [], "transactions": [], "patch_id": "fake-patch"},
                "execution_results": [],
                "errors": [],
                "warnings": [],
            }

    monkeypatch.setattr("app.routers.scene.creation_workflow.auto_execute_enabled", lambda: True)
    monkeypatch.setattr("app.routers.scene.creation_workflow.auto_execute_plan", lambda plan, patch_id=None: _FakeReport())

    client = _setup_client()
    response = client.post(
        "/scene/realize",
        json={
            "scene_id": "scene_lock_8",
            "player_id": "p1",
            "mode": "personal",
            "domain": "P1",
            "execution_mode": "execute",
            "anchor": {"x": 1000, "y": 64, "z": 0},
            "assets": [{"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 1000, "y": 64, "z": 0}}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["execution_mode"] == "execute"
    assert body["execution"]["mode"] == "execute"
    assert body["plan_id"] is not None
    assert body["patch_id"] is not None


def test_execute_readiness_reports_block_reasons(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    monkeypatch.delenv("DRIFT_SCENE_REALIZE_ALLOW_EXECUTE", raising=False)
    client = _setup_client()
    import app.routers.scene as scene_router

    monkeypatch.setattr(scene_router, "_rcon_available", lambda: False)
    monkeypatch.setattr(scene_router.creation_workflow, "auto_execute_enabled", lambda: False)

    response = client.get("/scene/execute-readiness", params={"player_id": "p1"})
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "allow_execute_flag",
        "rcon_available",
        "executor_ready",
        "mode",
        "policy_allow_execute",
        "can_execute",
        "reason",
    }
    assert body["allow_execute_flag"] is False
    assert body["rcon_available"] is False
    assert body["executor_ready"] is False
    assert body["policy_allow_execute"] is False
    assert body["can_execute"] is False
    assert "flag_disabled" in body["reason"]
    assert "rcon_unavailable" in body["reason"]


def test_execute_readiness_can_execute_when_all_ready(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    monkeypatch.setenv("DRIFT_SCENE_REALIZE_ALLOW_EXECUTE", "1")
    client = _setup_client()
    import app.routers.scene as scene_router

    monkeypatch.setattr(scene_router, "_rcon_available", lambda: True)
    monkeypatch.setattr(scene_router.creation_workflow, "auto_execute_enabled", lambda: True)

    response = client.get("/scene/execute-readiness", params={"player_id": "p1"})
    assert response.status_code == 200
    body = response.json()
    assert body["allow_execute_flag"] is True
    assert body["rcon_available"] is True
    assert body["executor_ready"] is True
    assert body["policy_allow_execute"] is False
    assert body["can_execute"] is True
    assert body["reason"] == []


def test_legacy_intent_execute_is_blocked(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    client = _setup_client()

    response = client.post(
        "/intent/execute",
        json={
            "message": "帮我建一个房子",
            "player_id": "p1",
            "dry_run_only": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["decision"]["legacy"] is True


def test_legacy_intent_plan_is_rejected(monkeypatch):
    monkeypatch.setenv("DRIFT_SCENE_REALIZATION_ONLY", "1")
    client = _setup_client()

    response = client.post("/intent/plan", json={"message": "帮我建一个房子"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["status"] == "blocked"
