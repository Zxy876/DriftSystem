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


#!/usr/bin/env python3
"""Minimal verification script for Step1 (run locally).

Tests:
- V1: apply vs advance equivalence (fresh snapshots)
- Reentrancy test: when is_applying=True, apply rejects as busy
- Snapshot test: apply emits an 'apply_snapshot' log record
- Concurrency smoke: two concurrent applies -> one busy
- Abort logging: advance() raises -> apply_aborted is logged

Usage: python3 scripts/step1_verify.py
"""
import sys
from pathlib import Path
import logging
import threading
import time
from typing import List

# Ensure script can be run from repo root without setting PYTHONPATH
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
# If project uses `backend/app` layout, prefer backend on sys.path so `app` imports resolve
backend_path = repo_root / "backend"
if backend_path.exists():
    sys.path.insert(0, str(backend_path))

from app.core.story.story_engine import story_engine


def reset_player(player_id: str):
    if player_id in story_engine.players:
        del story_engine.players[player_id]


def capture_logs(func, *args, **kwargs):
    logger = logging.getLogger()
    old_level = logger.level
    logger.setLevel(logging.INFO)
    records: List[logging.LogRecord] = []

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
    meta = patch.get("meta", {}) if isinstance(patch, dict) else {}
    assert tell and "Busy" in tell, f"Reentrancy rejection expected, got: {patch}"
    assert meta.get("status") == "busy", "Busy patch must include meta.status=busy"
    print("Reentrancy test: PASS")


def test_snapshot_logging():
    player_id = "step1_test_snapshot"
    reset_player(player_id)

    def call_apply():
        return story_engine.apply(player_id, {"variables": {}}, {"say": "x"})

    _, records = capture_logs(call_apply)
    found = False
    for r in records:
        if getattr(r, "msg", "") == "apply_snapshot":
            # snapshot log should include snapshot_digest
            assert hasattr(r, "snapshot_digest") or (isinstance(r.__dict__.get("snapshot_digest", None), str)), f"snapshot_digest missing in record: {r.__dict__}"
            found = True
            break
    assert found, f"apply_snapshot log not found in {len(records)} records"
    print("Snapshot logging test: PASS")


def test_concurrency_smoke():
    player_id = "step1_test_concurrency"
    reset_player(player_id)

    # Monkeypatch advance to hold the lock for a short time to simulate work
    original_advance = story_engine.advance

    def slow_advance(player_id_arg, world_state_arg, action_arg):
        time.sleep(0.25)
        return (None, None, {"mc": {"ok": True}})

    story_engine.advance = slow_advance

    results = []

    def call_apply():
        try:
            res = story_engine.apply(player_id, {"variables": {}}, {"say": "x"})
        except Exception as e:
            res = ("error", str(e))
        results.append(res)

    t1 = threading.Thread(target=call_apply)
    t2 = threading.Thread(target=call_apply)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Restore advance
    story_engine.advance = original_advance

    # Expect one success and one busy
    busy_count = 0
    ok_count = 0
    for r in results:
        if isinstance(r, tuple) and len(r) == 3:
            _, _, patch = r
            meta = patch.get("meta", {}) if isinstance(patch, dict) else {}
            if meta.get("status") == "busy":
                busy_count += 1
            else:
                ok_count += 1
        else:
            # error path
            pass

    assert busy_count == 1 and ok_count == 1, f"Expected 1 busy + 1 ok, got busy={busy_count} ok={ok_count} results={results}"
    print("Concurrency smoke test: PASS")


def test_abort_logging():
    player_id = "step1_test_abort"
    reset_player(player_id)

    # Monkeypatch advance to raise
    original_advance = story_engine.advance

    def raising_advance(player_id_arg, world_state_arg, action_arg):
        raise RuntimeError("simulated-advance-failure")

    story_engine.advance = raising_advance

    def call_apply():
        try:
            return story_engine.apply(player_id, {"variables": {}}, {"say": "x"})
        except Exception:
            # propagate for capture
            raise

    try:
        try:
            _, records = capture_logs(call_apply)
            # If no exception propagated, that's unexpected
            raise AssertionError("apply did not raise when advance raised")
        except Exception:
            # exception expected; inspect captured logs
            _, records = capture_logs(lambda: None)  # capture current logs (no-op)
    finally:
        story_engine.advance = original_advance

    # Now check that apply_aborted was logged in the earlier capture
    # We'll call apply again with a raising advance but capture logs directly
    story_engine.advance = raising_advance
    try:
        try:
            _, records = capture_logs(call_apply)
        except Exception:
            pass
    finally:
        story_engine.advance = original_advance

    found_abort = any(getattr(r, "msg", "") == "apply_aborted" or "apply_aborted" in (getattr(r, "message", "") or r.getMessage()) for r in records)
    assert found_abort, "apply_aborted not found in logs"
    print("Abort logging test: PASS")


def test_tx_history_success_and_busy():
    # success path
    player_id = "step2a_test_success"
    reset_player(player_id)
    res = story_engine.apply(player_id, {"variables": {}}, {"say": "x"})
    dq = getattr(story_engine, "_tx_history", {}).get(player_id)
    assert dq and len(dq) >= 1, f"tx_history missing for player {player_id}"
    rec = dq[-1]
    assert rec.get("status") == "success", f"expected success record, got {rec.get('status')}"
    assert rec.get("result_summary") is not None, "result_summary missing"
    assert rec.get("started_at") <= rec.get("finished_at"), "timestamps invalid"

    # busy path
    player_busy = "step2a_test_busy"
    reset_player(player_busy)

    original_advance = story_engine.advance

    def slow_advance(pid, ws, action):
        time.sleep(0.25)
        return (None, None, {"mc": {"ok": True}})

    story_engine.advance = slow_advance

    t = threading.Thread(target=lambda: story_engine.apply(player_busy, {"variables": {}}, {"say": "x"}))
    t.start()
    time.sleep(0.05)
    _, _, patch = story_engine.apply(player_busy, {"variables": {}}, {"say": "x"})
    meta = patch.get("meta", {}) if isinstance(patch, dict) else {}
    assert meta.get("status") == "busy", f"expected busy patch, got {patch}"
    dq_busy = getattr(story_engine, "_tx_history", {}).get(player_busy)
    assert dq_busy and any(r.get("status") == "busy" for r in dq_busy), "busy tx_record not found"

    story_engine.advance = original_advance
    t.join()
    print("Tx history tests: PASS")


if __name__ == "__main__":
    test_v1_equivalence()
    test_reentrancy()
    test_snapshot_logging()
    test_concurrency_smoke()
    test_abort_logging()
    test_tx_history_success_and_busy()
    print("All Step1 verifications passed.")
