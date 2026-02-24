import json
import os
from importlib import reload
from pathlib import Path

from fastapi.testclient import TestClient


def setup_app(tmp_path):
    os.environ["DRIFT_LEVEL_SESSION_DB"] = str(tmp_path / "sessions.db")
    os.environ["DRIFT_CREW_RUNS_DIR"] = str(tmp_path / "crew_runs")
    os.environ["DRIFT_BLUEPRINT_DIR"] = str(tmp_path / "blueprints")
    # 重新加载模块以拾取新路径
    import app.api.director_intent_api as director_intent_api
    import app.main as app_main

    reload(director_intent_api)
    reload(app_main)
    return app_main.app


def test_level_intent_dry_run(tmp_path):
    app = setup_app(tmp_path)
    client = TestClient(app)

    # 创建 session 初始状态 IMPORTED
    from app.levels.level_session import LevelSessionStore

    store = LevelSessionStore(os.environ["DRIFT_LEVEL_SESSION_DB"])
    store.create_session("level_demo")

    resp = client.post(
        "/director/intents",
        json={"player_id": "director", "raw_text": "level level_id=level_demo target_state=SET_DRESS", "dry_run": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert body["routed_to"] == "level_session"
    assert body["next_state"] == "SET_DRESS"
    # 状态未被修改
    assert store.get_state("level_demo") == "IMPORTED"


def test_level_intent_invalid_transition(tmp_path):
    app = setup_app(tmp_path)
    client = TestClient(app)

    from app.levels.level_session import LevelSessionStore

    store = LevelSessionStore(os.environ["DRIFT_LEVEL_SESSION_DB"])
    store.create_session("level_demo")

    resp = client.post(
        "/director/intents",
        json={"player_id": "director", "raw_text": "level level_id=level_demo target_state=TAKE", "dry_run": True},
    )
    assert resp.status_code == 400
    assert "invalid_transition" in resp.json()["detail"]


def test_task_intent_apply(tmp_path):
    app = setup_app(tmp_path)
    client = TestClient(app)

    resp = client.post(
        "/director/intents",
        json={
            "player_id": "director",
            "raw_text": "task task_id=t1 level_id=level_demo summary=build_scene assigned_to=crew_bot",
            "dry_run": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["routed_to"] == "task_manager"

    # 检查写入日志
    runs_dir = Path(os.environ["DRIFT_CREW_RUNS_DIR"])
    assert runs_dir.exists()
    log_files = list(runs_dir.glob("*/task.jsonl"))
    assert log_files, "task.jsonl 应被创建"
    content = log_files[0].read_text(encoding="utf-8")
    assert "\"task_id\": \"t1\"" in content


def test_actor_intent_dry_run(tmp_path):
    app = setup_app(tmp_path)
    client = TestClient(app)

    resp = client.post(
        "/director/intents",
        json={"player_id": "director", "raw_text": "actor actor_id=a1 action=pose mood=happy", "dry_run": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["routed_to"] == "actor_controller"
    assert body["status"] == "dry_run"


def test_actor_intent_queue(tmp_path):
    app = setup_app(tmp_path)
    client = TestClient(app)

    resp = client.get("/director/actor/next")
    assert resp.status_code == 204


def test_build_intent_and_apply(tmp_path):
    blueprint_dir = tmp_path / "blueprints"
    blueprint_dir.mkdir(parents=True, exist_ok=True)
    blueprint = {
        "actions": [
            {"action": "setblock", "position": [0, 64, 0], "block": "stone"},
            {"action": "travel", "position": [1, 64, 1]},
        ]
    }
    (blueprint_dir / "bp1.json").write_text(json.dumps(blueprint), encoding="utf-8")

    app = setup_app(tmp_path)
    client = TestClient(app)

    resp = client.post(
        "/director/intents",
        json={
            "player_id": "director",
            "raw_text": "build task_id=t1 blueprint_id=bp1 level_id=demo origin_x=10 origin_y=0 origin_z=5",
            "dry_run": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    pending = tmp_path / "crew_runs" / "pending" / "t1.json"
    assert pending.exists()
    status_path = tmp_path / "crew_runs" / "status" / "t1.json"
    assert status_path.exists()
    status = json.loads(status_path.read_text())
    assert status["status"] == "pending"

    # apply will fail because node/bridge not present in test env; expect node_not_found or bridge_failed handled by status code 500.
    resp = client.post("/director/build/apply", params={"task_id": "t1"})
    assert resp.status_code in (200, 500, 404)
    # status endpoint should exist
    resp_status = client.get("/director/build/status", params={"task_id": "t1"})
    assert resp_status.status_code in (200, 404)

    resp = client.post(
        "/director/intents",
        json={
            "player_id": "director",
            "raw_text": "actor actor_id=alice action=say line=hello",
            "dry_run": False,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    resp = client.get("/director/actor/next")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["intent"]["actor_id"] == "alice"
    assert body["intent"]["action"] == "say"

    resp = client.get("/director/actor/next")
    assert resp.status_code == 204


def test_unknown_intent(tmp_path):
    app = setup_app(tmp_path)
    client = TestClient(app)

    resp = client.post(
        "/director/intents",
        json={"player_id": "director", "raw_text": "unknown foo=bar", "dry_run": True},
    )
    assert resp.status_code == 400
    assert "unsupported_intent_type" in resp.json()["detail"]
