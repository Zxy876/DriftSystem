import json
from pathlib import Path

from app.core.ideal_city.manifestation_intent import ManifestationIntent
from app.core.ideal_city.manifestation_writer import ManifestationIntentWriter


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_write_intent_envelope_and_audit(tmp_path: Path) -> None:
    writer = ManifestationIntentWriter(tmp_path, enable_audit=True)
    intent = ManifestationIntent.create(
        scenario_id="default",
        allowed_stage=2,
        constraints=["no_stage_skip"],
        context_notes=["示例 context"],
    )

    path = writer.write_intent(intent, player_id="player-uuid", spec_id="spec-123")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["player_id"] == "player-uuid"
    assert payload["intent"]["allowed_stage"] == 2
    assert payload["intent"].get("metadata", {}).get("source_spec_id") == "spec-123"

    audit_entries = _read_jsonl(tmp_path / "city-intents" / "intent_audit.jsonl")
    assert audit_entries
    assert audit_entries[-1]["intent"]["intent_id"] == intent.intent_id
    assert audit_entries[-1]["metadata"]["storage"] == "city-intents/pending"
