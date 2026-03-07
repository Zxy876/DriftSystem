from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
PLAYER_ID = "vivn"
REQUEST_TIMEOUT_SECONDS = 90
PHRASES = [
    "创建剧情 大风吹",
    "创建剧情 暴风雨",
    "创建剧情 大风吹 在森林里",
    "创建剧情 暴风雨 在海边",
]


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run() -> None:
    print("=== Phase7 live acceptance probe ===")
    for index, phrase in enumerate(PHRASES, start=1):
        print(f"\n[{index}] {phrase}")

        try:
            intent_resp = post(
                "/ai/intent",
                {
                    "player_id": PLAYER_ID,
                    "text": phrase,
                    "world_state": {},
                },
            )
        except Exception as exc:
            print("intent_error:", str(exc))
            continue
        first_intent = (intent_resp.get("intents") or [{}])[0]
        scene_theme = first_intent.get("scene_theme")
        scene_hint = first_intent.get("scene_hint")

        print(
            "intent:",
            {
                "type": first_intent.get("type"),
                "scene_theme": scene_theme,
                "scene_hint": scene_hint,
            },
        )

        level_id = f"phase7_live_accept_{int(time.time() * 1000)}_{index}"
        inject_payload = {
            "level_id": level_id,
            "title": f"验收-{index}",
            "text": phrase,
            "player_id": PLAYER_ID,
        }
        if scene_theme:
            inject_payload["scene_theme"] = scene_theme
        if scene_hint:
            inject_payload["scene_hint"] = scene_hint

        try:
            inject_resp = post("/story/inject", inject_payload)
        except Exception as exc:
            print("inject_error:", str(exc))
            continue
        scene = inject_resp.get("scene") or {}
        scene_plan = scene.get("scene_plan") or {}
        event_plan = scene.get("event_plan") or []
        first_event_data = (event_plan[0].get("data") if event_plan else {}) or {}

        meta_scene = {}
        file_path = inject_resp.get("file")
        if isinstance(file_path, str) and Path(file_path).exists():
            level_doc = json.loads(Path(file_path).read_text(encoding="utf-8"))
            meta_scene = ((level_doc.get("meta") or {}).get("scene_generation") or {})

        print(
            "inject:",
            {
                "status": inject_resp.get("status"),
                "level_id": inject_resp.get("level_id"),
                "scene_theme": scene.get("scene_theme"),
                "scene_hint": scene.get("scene_hint"),
                "fragments": scene_plan.get("fragments"),
                "event_ids": [evt.get("event_id") for evt in event_plan],
                "event_hint": first_event_data.get("scene_hint"),
                "event_variant": first_event_data.get("scene_variant"),
                "meta_scene_theme": meta_scene.get("scene_theme"),
                "meta_scene_hint": meta_scene.get("scene_hint"),
            },
        )

    print("\n=== probe completed ===")


if __name__ == "__main__":
    run()
