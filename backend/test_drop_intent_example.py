import json
from pathlib import Path
from typing import Sequence

from scripts.drop_intent_example import main as drop_intent_main


def run_drop_intent(tmp_path: Path, extra_args: Sequence[str] | None = None) -> Path:
    protocol_root = tmp_path / "protocol"
    argv = [
        "--player-id",
        "test-player",
        "--scenario-id",
        "scenario-x",
        "--stage",
        "3",
        "--protocol-root",
        str(protocol_root),
    ]
    if extra_args:
        argv.extend(extra_args)
    drop_intent_main(argv)
    return protocol_root / "city-intents" / "pending"


def test_drop_intent_produces_envelope(tmp_path: Path) -> None:
    pending_dir = run_drop_intent(tmp_path)
    files = list(pending_dir.glob("*.json"))
    assert files, "Expected an intent file in pending directory"
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["player_id"] == "test-player"
    assert payload["intent"]["scenario_id"] == "scenario-x"
    assert payload["intent"]["allowed_stage"] == 3


def test_drop_intent_dry_run(tmp_path: Path, capsys) -> None:
    argv = [
        "--player-id",
        "dry-player",
        "--scenario-id",
        "scenario-dry",
        "--stage",
        "4",
        "--dry-run",
    ]
    drop_intent_main(argv)
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert payload["intent"]["allowed_stage"] == 4