#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://driftsystem-production.up.railway.app}"
PLAYER_ID="${PLAYER_ID:-smoke_scene_runner}"
TITLE="${TITLE:-线上冒烟-夜市向导}"
TEXT="${TEXT:-请导入剧情：夜晚湖边有向导和两盏灯}"
EXECUTE_CONFIRM="${EXECUTE_CONFIRM:-false}"
REQUIRE_SCENE_STATUS_OK="${REQUIRE_SCENE_STATUS_OK:-0}"

python3 - <<'PY'
import json
import os
import sys
import time
import requests

base = os.environ.get("BASE_URL", "https://driftsystem-production.up.railway.app")
player_id = os.environ.get("PLAYER_ID", "smoke_scene_runner")
title = os.environ.get("TITLE", "线上冒烟-夜市向导")
text = os.environ.get("TEXT", "请导入剧情：夜晚湖边有向导和两盏灯")
execute_confirm = os.environ.get("EXECUTE_CONFIRM", "false").strip().lower() in {"1", "true", "yes", "on"}
require_scene_ok = os.environ.get("REQUIRE_SCENE_STATUS_OK", "0").strip().lower() in {"1", "true", "yes", "on"}

level_id = f"flagship_custom_smoke_{int(time.time())}"
result = {"base_url": base, "level_id": level_id}

try:
    quota = requests.get(f"{base}/ai/quota-status", timeout=20)
    result["quota_status"] = quota.status_code
    if quota.ok:
        result["quota_model"] = quota.json().get("model")
except Exception as exc:
    print(json.dumps({"status": "error", "stage": "quota", "error": str(exc)}, ensure_ascii=False, indent=2))
    sys.exit(1)

payload = {
    "level_id": level_id,
    "title": title,
    "text": text,
    "player_id": player_id,
    "execute_confirm": execute_confirm,
}

inject = requests.post(f"{base}/story/inject", json=payload, timeout=60)
result["inject_status"] = inject.status_code
if inject.status_code != 200:
    print(json.dumps({"status": "error", "stage": "inject", "http": inject.status_code, "body": inject.text[:1200]}, ensure_ascii=False, indent=2))
    sys.exit(2)

inject_json = inject.json()
world_preview = inject_json.get("world_preview") if isinstance(inject_json, dict) else {}
scene_status_obj = inject_json.get("scene_status") if isinstance(inject_json, dict) else {}
scene_status = scene_status_obj.get("status") if isinstance(scene_status_obj, dict) else None
result["inject"] = {
    "status": inject_json.get("status"),
    "level_id": inject_json.get("level_id"),
    "scene_status": scene_status,
    "scene_errors": scene_status_obj.get("errors") if isinstance(scene_status_obj, dict) else None,
    "scene_needs_review": scene_status_obj.get("needs_review") if isinstance(scene_status_obj, dict) else None,
    "world_preview_keys": sorted(list(world_preview.keys())) if isinstance(world_preview, dict) else [],
    "has_spawn_multi": isinstance(world_preview.get("spawn_multi"), list) if isinstance(world_preview, dict) else False,
    "has_commands": isinstance(world_preview.get("commands"), list) if isinstance(world_preview, dict) else False,
}

loaded = requests.post(f"{base}/story/load/{player_id}/{inject_json.get('level_id', level_id)}", timeout=30)
result["load_status"] = loaded.status_code
if loaded.status_code != 200:
    print(json.dumps({"status": "error", "stage": "load", "http": loaded.status_code, "body": loaded.text[:1200], "partial": result}, ensure_ascii=False, indent=2))
    sys.exit(3)

load_json = loaded.json()
mc = ((load_json.get("bootstrap_patch") or {}).get("mc") or {}) if isinstance(load_json, dict) else {}
result["load"] = {
    "status": load_json.get("status"),
    "msg": load_json.get("msg"),
    "bootstrap_mc_keys": sorted(list(mc.keys())) if isinstance(mc, dict) else [],
    "has_spawn_multi": isinstance(mc.get("spawn_multi"), list) if isinstance(mc, dict) else False,
    "has_commands": isinstance(mc.get("commands"), list) if isinstance(mc, dict) else False,
}

ok = (
    result.get("quota_status") == 200
    and result.get("inject_status") == 200
    and result.get("load_status") == 200
    and result["inject"]["has_spawn_multi"]
    and result["inject"]["has_commands"]
    and result["load"]["has_spawn_multi"]
    and result["load"]["has_commands"]
)

if require_scene_ok:
    ok = ok and scene_status == "ok"

result["status"] = "ok" if ok else "failed"
print(json.dumps(result, ensure_ascii=False, indent=2))
if not ok:
    sys.exit(4)
PY
