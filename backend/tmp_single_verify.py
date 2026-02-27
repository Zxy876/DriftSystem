import json
import time
import requests

base = "https://driftsystem-production.up.railway.app"
payload = {
    "level_id": f"flagship_single_verify_{int(time.time())}",
    "title": "单人记忆验收",
    "text": "请导入剧情：我和爷爷在院子里修风筝，然后继续和我对话",
    "player_id": "single_verify_u1",
    "execute_confirm": False,
}

response = requests.post(f"{base}/story/inject", json=payload, timeout=60)
body = response.json()
mc = body.get("world_preview", {}) if isinstance(body, dict) else {}
scene_status = body.get("scene_status", {}) if isinstance(body, dict) else {}

print(
    json.dumps(
        {
            "http": response.status_code,
            "scene_status": scene_status.get("status") if isinstance(scene_status, dict) else scene_status,
            "has_build": "build" in mc,
            "has_commands": isinstance(mc.get("commands"), list) and len(mc.get("commands", [])) > 0,
            "has_spawn_multi": isinstance(mc.get("spawn_multi"), list) and len(mc.get("spawn_multi", [])) > 0,
            "has_title": isinstance(mc.get("title"), dict),
            "keys": sorted(list(mc.keys())) if isinstance(mc, dict) else [],
        },
        ensure_ascii=False,
        indent=2,
    )
)
