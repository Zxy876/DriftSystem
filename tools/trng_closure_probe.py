from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"


def post(path: str, payload: dict) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get(path: str) -> dict:
    req = urllib.request.Request(BASE + path, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run() -> int:
    now = int(time.time())
    player = f"trng_loop_probe_{now}"
    level_id = f"trng_loop_level_{now}"
    build_id = f"build_{int(time.time() * 1000)}"

    rule_resp = post(
        "/world/story/rule-event",
        {
            "player_id": player,
            "event_type": "collect",
            "payload": {
                "item_type": "wood",
                "resource": "wood",
                "amount": 2,
                "quest_event": "collect_wood",
                "location": {"x": 5, "y": 64, "z": 5},
            },
        },
    )

    inject_resp = post(
        "/story/inject",
        {
            "level_id": level_id,
            "title": "TRNG闭环探针",
            "text": "创建剧情 大风吹 在森林里",
            "player_id": player,
            "scene_theme": "大风吹",
            "scene_hint": "森林",
        },
    )

    load_resp = post(f"/story/load/{urllib.parse.quote(player)}/{urllib.parse.quote(level_id)}", {})
    bootstrap_patch = load_resp.get("bootstrap_patch") if isinstance(load_resp, dict) else None
    mc_patch = (bootstrap_patch or {}).get("mc") if isinstance(bootstrap_patch, dict) else {}

    executed = 0
    for key in ("spawn_multi", "build_multi", "blocks", "structure"):
        value = mc_patch.get(key) if isinstance(mc_patch, dict) else None
        if isinstance(value, list):
            executed += len(value)
    if isinstance(mc_patch, dict) and isinstance(mc_patch.get("spawn"), dict):
        executed += 1
    if executed <= 0:
        executed = 1

    report_resp = post(
        "/world/apply/report",
        {
            "build_id": build_id,
            "player_id": player,
            "status": "EXECUTED",
            "failure_code": "NONE",
            "executed": executed,
            "failed": 0,
            "duration_ms": 120,
            "payload_hash": f"hash_{int(time.time())}",
        },
    )

    state_resp = get(f"/world/state/{urllib.parse.quote(player)}")
    debug_resp = get(f"/world/story/{urllib.parse.quote(player)}/debug/tasks")

    interaction_tx = rule_resp.get("interaction_transaction") if isinstance(rule_resp, dict) else None
    inject_tx = inject_resp.get("transaction") if isinstance(inject_resp, dict) else None
    scene_world_patch = inject_resp.get("scene_world_patch") if isinstance(inject_resp, dict) else None
    last_apply_report = debug_resp.get("last_apply_report") if isinstance(debug_resp, dict) else None

    checks = {
        "event_to_transaction": bool(interaction_tx and interaction_tx.get("tx_id")),
        "inject_transaction": bool(inject_tx and inject_tx.get("tx_id")),
        "transaction_to_world_patch": bool(
            isinstance(scene_world_patch, dict) and (scene_world_patch.get("mc") or {})
        ),
        "world_patch_to_minecraft_load": bool(
            isinstance(load_resp, dict)
            and load_resp.get("status") == "ok"
            and isinstance(bootstrap_patch, dict)
        ),
        "minecraft_to_state_update": bool(
            isinstance(report_resp, dict)
            and report_resp.get("accepted")
            and isinstance(last_apply_report, dict)
            and last_apply_report.get("build_id") == build_id
        ),
    }

    print("player_id:", player)
    print("level_id:", level_id)
    print("build_id:", build_id)
    print("checks:", json.dumps(checks, ensure_ascii=False))
    print("rule_event_status:", rule_resp.get("status") if isinstance(rule_resp, dict) else None)
    print("rule_event_tx_id:", (interaction_tx or {}).get("tx_id"))
    print("inject_status:", inject_resp.get("status") if isinstance(inject_resp, dict) else None)
    print("inject_tx_id:", (inject_tx or {}).get("tx_id"))
    scene = inject_resp.get("scene") if isinstance(inject_resp, dict) else None
    scene_events = (scene or {}).get("event_plan") if isinstance(scene, dict) else []
    print("scene_event_count:", len(scene_events) if isinstance(scene_events, list) else 0)
    print("load_status:", load_resp.get("status") if isinstance(load_resp, dict) else None)
    print("bootstrap_mc_keys:", sorted(list(mc_patch.keys())) if isinstance(mc_patch, dict) else [])
    print(
        "apply_report_status:",
        report_resp.get("status") if isinstance(report_resp, dict) else None,
        "accepted:",
        report_resp.get("accepted") if isinstance(report_resp, dict) else None,
    )
    print("debug_status:", debug_resp.get("status") if isinstance(debug_resp, dict) else None)
    print("debug_last_apply_build_id:", (last_apply_report or {}).get("build_id"))
    print("world_state_status:", state_resp.get("status") if isinstance(state_resp, dict) else None)

    if not all(checks.values()):
        print("TRNG loop probe failed:", json.dumps(checks, ensure_ascii=False))
        return 1

    print("TRNG loop probe passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
