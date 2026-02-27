#!/usr/bin/env python3
"""Minimal verification script for Step1 (run locally).

Tests:
- V1: apply vs advance equivalence (fresh snapshots)
- Reentrancy test: when is_applying=True, apply rejects as busy
- Snapshot test: apply emits an 'apply_snapshot' log record

Usage: python3 scripts/step1_verify.py
"""
import logging
from app.core.story.story_engine import story_engine


def reset_player(player_id: str):
    if player_id in story_engine.players:
        del story_engine.players[player_id]


def capture_logs(func, *args, **kwargs):
    logger = logging.getLogger()
    old_level = logger.level
    logger.setLevel(logging.INFO)
    records = []

    class CaptHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    h = CaptHandler()
    logger.addHandler(h)
    try:
        result = func(*args, **kwargs)
    finally:
        logger.removeHandler(h)
        logger.setLevel(old_level)
    return result, records


def test_v1_equivalence():
    player_id = "step1_test"
    world_state = {"variables": {"x": 0, "y": 64, "z": 0}}
    action = {"say": "hello world"}

    # direct advance on fresh player
    reset_player(player_id)
    res_adv = story_engine.advance(player_id, world_state, action)

    # apply on fresh player
    reset_player(player_id)
    res_apply = story_engine.apply(player_id, world_state, action)

    assert res_adv == res_apply, f"advance != apply: {res_adv} vs {res_apply}"
    print("V1 equivalence: PASS")


def test_reentrancy():
    player_id = "step1_test_reentrancy"
    reset_player(player_id)
    story_engine._ensure_player(player_id)
    p = story_engine.players[player_id]
    p["is_applying"] = True
    _, _, patch = story_engine.apply(player_id, {"variables": {}}, {})
    mc = patch.get("mc", {}) if isinstance(patch, dict) else {}
    tell = mc.get("tell") if isinstance(mc, dict) else None
    assert tell and "Busy" in tell, f"Reentrancy rejection expected, got: {patch}"
    print("Reentrancy test: PASS")


def test_snapshot_logging():
    player_id = "step1_test_snapshot"
    reset_player(player_id)
    def call_apply():
        return story_engine.apply(player_id, {"variables": {}}, {"say": "x"})

    _, records = capture_logs(call_apply)
    found = any(getattr(r, "msg", "") == "apply_snapshot" or "apply_snapshot" in (getattr(r, "message", "") or r.getMessage()) for r in records)
    assert found, f"apply_snapshot log not found in {len(records)} records"
    print("Snapshot logging test: PASS")


if __name__ == "__main__":
    test_v1_equivalence()
    test_reentrancy()
    test_snapshot_logging()
    print("All Step1 verifications passed.")
