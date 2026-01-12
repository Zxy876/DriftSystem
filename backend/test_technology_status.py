import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.ideal_city.technology_status import TechnologyStatusRepository


def test_technology_status_repository_empty(tmp_path: Path) -> None:
    repo = TechnologyStatusRepository(tmp_path)
    snapshot = repo.load_snapshot()
    assert snapshot.stage is None
    assert snapshot.energy is None
    assert snapshot.risk_alerts == []
    assert snapshot.recent_events == []
    assert snapshot.updated_at is None


def test_technology_status_repository_parses_payload(tmp_path: Path) -> None:
    repo = TechnologyStatusRepository(tmp_path)
    data = {
        "stage": {"label": "阶段 2 — 紫水晶精炼", "level": 2, "progress": 0.45},
        "energy": {"generation": 128.4, "consumption": 96.2, "capacity": 240, "reserve": 18.5},
        "risks": [
            {"risk_id": "overload", "level": "warning", "summary": "晶体反应室温度趋于上升"},
            {"id": "supply", "severity": "info", "description": "高纯度紫水晶库存紧张"},
        ],
        "recent_events": [
            {
                "event_id": "evt-001",
                "category": "construction",
                "description": "完成精炼塔稳压单元升级",
                "occurred_at": "2026-01-09T12:00:00+00:00",
                "impact": "positive",
            },
            {
                "id": "evt-000",
                "type": "audit",
                "summary": "完成阶段 1 审计",
                "timestamp": "2026-01-08T10:00:00Z",
            },
        ],
        "updated_at": "2026-01-09T12:30:00Z",
    }
    (tmp_path / "technology-status.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    snapshot = repo.load_snapshot()

    assert snapshot.stage is not None
    assert snapshot.stage.label.startswith("阶段 2")
    assert snapshot.stage.level == 2
    assert snapshot.stage.progress == 0.45
    assert snapshot.energy is not None
    assert snapshot.energy.generation == 128.4
    assert snapshot.energy.consumption == 96.2
    assert snapshot.energy.capacity == 240.0
    assert snapshot.energy.storage == 18.5
    assert len(snapshot.risk_alerts) == 2
    assert snapshot.risk_alerts[0].risk_id == "overload"
    assert snapshot.risk_alerts[1].risk_id == "supply"
    assert snapshot.risk_alerts[1].level == "info"
    assert snapshot.recent_events[0].event_id == "evt-001"
    assert snapshot.recent_events[0].impact == "positive"
    assert snapshot.recent_events[0].occurred_at == datetime(2026, 1, 9, 12, 0, tzinfo=timezone.utc)
    assert snapshot.recent_events[1].category == "audit"
    assert snapshot.updated_at == datetime(2026, 1, 9, 12, 30, tzinfo=timezone.utc)


def test_technology_status_repository_accepts_forge_bundle_sample(tmp_path: Path) -> None:
    repo = TechnologyStatusRepository(tmp_path)
    sample = {
        "timestamp": "2026-01-10T05:51:11.891480+00:00",
        "updated_at": "2026-01-10T05:51:11.891480+00:00",
        "stage": {
            "current": 1,
            "level": 1,
            "label": "materialization",
            "scenario_id": "default",
            "scenario_version": "2026.01",
            "updated_at": "2026-01-10T05:51:11.891480+00:00",
            "source": "protocol-simulator",
        },
        "energy": {
            "status": "stable",
            "level": 75,
            "updated_at": "2026-01-10T05:51:11.891480+00:00",
            "generation": 120.0,
            "consumption": 95.0,
            "reserve": 40.0,
        },
        "risks": [],
        "alerts": [],
        "recent_events": [
            {
                "type": "stage_advance",
                "stage": 1,
                "label": "materialization",
                "scenario_id": "default",
                "scenario_version": "2026.01",
                "player_id": "00000000-0000-0000-0000-000000000000",
                "summary": "Stage 1 manifested by simulator",
                "occurred_at": "2026-01-10T05:51:11.891480+00:00",
            }
        ],
    }
    (tmp_path / "technology-status.json").write_text(
        json.dumps(sample, ensure_ascii=False),
        encoding="utf-8",
    )

    snapshot = repo.load_snapshot()

    assert snapshot.stage is not None
    assert snapshot.stage.level == 1
    assert snapshot.stage.label == "materialization"
    assert snapshot.energy is not None
    assert snapshot.energy.consumption == 95.0
    assert snapshot.energy.storage == 40.0
    assert snapshot.updated_at == datetime(2026, 1, 10, 5, 51, 11, 891480, tzinfo=timezone.utc)
    assert snapshot.recent_events
    event = snapshot.recent_events[0]
    assert event.category == "stage_advance"
    assert event.event_id.startswith("stage_advance-")
    assert event.occurred_at == datetime(2026, 1, 10, 5, 51, 11, 891480, tzinfo=timezone.utc)
