import json
import sys
import time
import uuid
from pathlib import Path
from urllib import error, request


BASE = "http://127.0.0.1:8000"
NO_PROXY_OPENER = request.build_opener(request.ProxyHandler({}))


def request_json(method: str, path: str, body: dict | None = None, timeout: int = 30) -> tuple[int, dict]:
    data = None
    headers: dict[str, str] = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(BASE + path, data=data, headers=headers, method=method.upper())
    try:
        with NO_PROXY_OPENER.open(req, timeout=timeout) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw}
        return int(exc.code), parsed


def post(path: str, body: dict, timeout: int = 30) -> tuple[int, dict]:
    return request_json("POST", path, body=body, timeout=timeout)


def get(path: str, timeout: int = 30) -> tuple[int, dict]:
    return request_json("GET", path, body=None, timeout=timeout)


def build_scene_locally(player_id: str) -> tuple[dict, list[str], dict[str, int]]:
    root = Path(__file__).resolve().parents[1]
    backend = root / "backend"
    for candidate in (str(root), str(backend)):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

    from app.api import story_api

    local_scene = story_api.build_scene_events(
        player_id=player_id,
        scene_theme="大风吹",
        scene_hint="森林",
        text="创建剧情 森林营地，验证资源语义",
        anchor=None,
        player_position={"world": "world", "x": 12.0, "y": 65.0, "z": -3.0},
    )
    fragments = list(((local_scene.get("scene_plan") or {}).get("fragments") or []))
    resources = dict(((local_scene.get("inventory_state") or {}).get("resources") or {}))
    return local_scene, fragments, resources


player = f"p2rt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
level_id = f"rt_p2_{int(time.time())}_{uuid.uuid4().hex[:4]}"

print("PLAYER", player)
print("LEVEL", level_id)

code_start, start_resp = post("/world/story/start", {"player_id": player})
print("START_STATUS", code_start, start_resp.get("status"), start_resp.get("level_id"))

collect_events = [
    {
        "event_type": "collect",
        "payload": {
            "item_type": "oak_log",
            "amount": 1,
            "location": {"x": 12, "y": 65, "z": -3, "world": "world"},
        },
    },
    {
        "event_type": "collect",
        "payload": {
            "item_type": "raw_porkchop",
            "amount": 1,
            "location": {"x": 12, "y": 65, "z": -3, "world": "world"},
        },
    },
    {
        "event_type": "collect",
        "payload": {
            "item_type": "torch",
            "amount": 1,
            "location": {"x": 12, "y": 65, "z": -3, "world": "world"},
        },
    },
]

for idx, event in enumerate(collect_events, start=1):
    code_collect, collect_resp = post("/world/story/rule-event", {"player_id": player, **event})
    print(f"COLLECT_{idx}", code_collect, collect_resp.get("status"), (event["payload"] or {}).get("item_type"))

code_debug_collect, debug_collect = get(f"/world/story/{player}/debug/tasks")
inventory_after_collect = dict(debug_collect.get("inventory_resources") or {})
print("DEBUG_AFTER_COLLECT_STATUS", code_debug_collect, debug_collect.get("status"))
print("DEBUG_AFTER_COLLECT_INVENTORY", json.dumps(inventory_after_collect, ensure_ascii=False, sort_keys=True))

canonical_inventory_ok = (
    int(inventory_after_collect.get("wood", 0)) >= 1
    and int(inventory_after_collect.get("pork", 0)) >= 1
    and int(inventory_after_collect.get("torch", 0)) >= 1
    and "oak_log" not in inventory_after_collect
    and "raw_porkchop" not in inventory_after_collect
)
print("CANONICAL_INVENTORY_OK", canonical_inventory_ok)

inject_payload = {
    "level_id": level_id,
    "title": "P2 Runtime Acceptance",
    "text": "创建剧情 森林营地，验证资源语义",
    "player_id": player,
    "player_position": {"world": "world", "x": 12.0, "y": 65.0, "z": -3.0},
    "scene_theme": "大风吹",
    "scene_hint": "森林",
}

inject_source = "api_inject"
inject_status = None
inject_response: dict = {}
scene_fragments: list[str] = []
scene_inventory: dict[str, int] = {}

try:
    inject_status, inject_response = post("/story/inject", inject_payload, timeout=20)
    print("INJECT_STATUS", inject_status, inject_response.get("status"), inject_response.get("detail"))
    scene_data = inject_response.get("scene") if isinstance(inject_response.get("scene"), dict) else {}
    scene_plan = scene_data.get("scene_plan") if isinstance(scene_data.get("scene_plan"), dict) else {}
    scene_fragments = list(scene_plan.get("fragments") or [])
    scene_inventory = dict((scene_data.get("inventory_state") or {}).get("resources") or {})
except TimeoutError:
    inject_source = "local_fallback_timeout"
    print("INJECT_TIMEOUT", True)

if not scene_fragments:
    inject_source = "local_fallback" if inject_source == "api_inject" else inject_source
    local_scene, scene_fragments, scene_inventory = build_scene_locally(player)
    print("LOCAL_SCENE_FALLBACK", True)
    print("LOCAL_SCENE_SELECTED_ANCHOR", local_scene.get("selected_anchor"))

print("SCENE_SOURCE", inject_source)
print("SCENE_INVENTORY", json.dumps(scene_inventory, ensure_ascii=False, sort_keys=True))
print("SCENE_FRAGMENTS", json.dumps(scene_fragments, ensure_ascii=False))

build_id = f"rt_accept_{int(time.time())}_{uuid.uuid4().hex[:6]}"
apply_report_payload = {
    "build_id": build_id,
    "player_id": player,
    "status": "EXECUTED",
    "failure_code": "OK",
    "executed": 4,
    "failed": 0,
    "duration_ms": 120,
    "payload_hash": uuid.uuid4().hex,
}
code_apply, apply_resp = post("/world/apply/report", apply_report_payload)
print("APPLY_REPORT_STATUS", code_apply, apply_resp.get("status"), apply_resp.get("last_status"))

code_debug_final, debug_final = get(f"/world/story/{player}/debug/tasks")
last_report = debug_final.get("last_apply_report") if isinstance(debug_final.get("last_apply_report"), dict) else {}
debug_scene = debug_final.get("scene_generation") if isinstance(debug_final.get("scene_generation"), dict) else {}

print("DEBUG_FINAL_STATUS", code_debug_final, debug_final.get("status"))
print("DEBUG_FINAL_LAST_APPLY", json.dumps(last_report, ensure_ascii=False, sort_keys=True))
print("DEBUG_FINAL_SCENE_FRAGMENTS", json.dumps(debug_scene.get("fragments") or [], ensure_ascii=False))

required_fragments = {"camp", "fire", "cooking_area"}
scene_fragments_ok = required_fragments.issubset(set(scene_fragments))

print(
    "RESULT_SUMMARY",
    json.dumps(
        {
            "player_id": player,
            "level_id": level_id,
            "canonical_inventory_ok": canonical_inventory_ok,
            "scene_source": inject_source,
            "scene_fragments": scene_fragments,
            "scene_fragments_ok": scene_fragments_ok,
            "apply_last_status": last_report.get("last_status"),
            "apply_last_failed": last_report.get("last_failed"),
        },
        ensure_ascii=False,
        sort_keys=True,
    ),
)
