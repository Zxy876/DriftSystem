from __future__ import annotations

import json
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parent / "data" / "intent" / "creation_intent_dataset.jsonl"


def test_creation_dataset_exists() -> None:
    assert DATASET_PATH.exists(), f"missing dataset at {DATASET_PATH}"


def test_creation_dataset_stats() -> None:
    lines = DATASET_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 100, f"dataset too small: {len(lines)}"

    labels = {"creation": 0, "non_creation": 0}
    for line in lines:
        payload = json.loads(line)
        label = payload.get("label")
        assert label in labels, f"unexpected label: {label}"
        labels[label] += 1
        assert isinstance(payload.get("message"), str) and payload["message"].strip()

    assert labels["creation"] > labels["non_creation"], "should have more creation samples"
    assert labels["non_creation"] >= 30, "non_creation coverage insufficient"
