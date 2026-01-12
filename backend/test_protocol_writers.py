import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.ideal_city.social_feedback import SocialFeedbackRepository
from app.core.ideal_city.social_feed_writer import SocialFeedWriter
from app.core.ideal_city.technology_status import TechnologyStatusRepository
from app.core.ideal_city.technology_status_writer import (
    EnergySnapshot,
    RiskEvent,
    StageSnapshot,
    TechnologyEvent,
    TechnologyStatusWriter,
)


def test_technology_status_writer_roundtrip(tmp_path: Path) -> None:
    writer = TechnologyStatusWriter(tmp_path)
    stage = StageSnapshot(level=2, label="Crystal Bloom", progress=0.42)
    writer.update_stage(stage, updated_at=datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc))
    writer.update_energy(EnergySnapshot(generation=180, consumption=120, capacity=250, storage=88))
    writer.record_risk(RiskEvent(risk_id="overheat", level="medium", summary="Thermal variance"))
    writer.record_event(
        TechnologyEvent(
            event_id="evt-stage",
            category="stage_update",
            description="Forge advanced to bloom stage",
            occurred_at=datetime(2026, 1, 10, 12, 5, tzinfo=timezone.utc),
            impact="positive",
        )
    )

    repo = TechnologyStatusRepository(tmp_path)
    snapshot = repo.load_snapshot()
    assert snapshot.stage is not None
    assert snapshot.stage.level == 2
    assert snapshot.energy is not None
    assert snapshot.energy.generation == 180
    assert len(snapshot.risk_alerts) == 1
    assert snapshot.risk_alerts[0].risk_id == "overheat"
    assert len(snapshot.recent_events) == 1
    assert snapshot.updated_at is not None


def test_social_feed_writer_roundtrip(tmp_path: Path) -> None:
    writer = SocialFeedWriter(tmp_path)
    issued_at = datetime(2026, 1, 10, 9, 30, tzinfo=timezone.utc)
    appended = writer.append_event(
        entry_id="stage_advance_demo",
        category="praise",
        title="Stage advanced to 2",
        body="Forge validated stage advancement.",
        issued_at=issued_at,
        stage=2,
        trust_delta=0.12,
        stress_delta=-0.03,
        tags=["stage", "demo"],
    )
    assert appended is True

    writer.set_metrics(trust_index=0.78, stress_index=0.19, updated_at=datetime(2026, 1, 10, 9, 31, tzinfo=timezone.utc))

    repo = SocialFeedbackRepository(tmp_path)
    snapshot = repo.load_snapshot(limit=10)
    assert snapshot.entries
    entry = snapshot.entries[0]
    assert entry.entry_id == "stage_advance_demo"
    assert entry.stage == 2
    assert snapshot.trust_index == 0.78
    assert snapshot.stress_index == 0.19
    assert snapshot.updated_at is not None

    # duplicates should be rejected by default
    second_append = writer.append_event(
        entry_id="stage_advance_demo",
        category="praise",
        title="Duplicate",
        body="Should be ignored",
        issued_at=issued_at,
    )
    assert second_append is False

    # ensure metrics file is stored as JSON
    metrics_path = tmp_path / "cityphone" / "social-feed" / "metrics.json"
    with metrics_path.open("r", encoding="utf-8") as handle:
        metrics_payload = json.load(handle)
    assert metrics_payload["trust_index"] == 0.78
