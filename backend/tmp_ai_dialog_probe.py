import json
import requests

BASE = "https://driftsystem-production.up.railway.app"
PLAYER = "diag_dialog_u1"

start = requests.post(f"{BASE}/world/story/start", json={"player_id": PLAYER}, timeout=30)

turns = []
for text in [
    "我想和爷爷聊聊我们一起修风筝的回忆",
    "那天黄昏我们为什么会争吵？",
    "你能给我一个下一步行动建议吗？",
]:
    payload = {
        "player_id": PLAYER,
        "action": {"say": text},
        "world_state": {"variables": {"x": 0, "y": 64, "z": 0}},
    }
    resp = requests.post(f"{BASE}/world/apply", json=payload, timeout=45)
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    node = body.get("story_node") or {}
    turns.append(
        {
            "input": text,
            "status": resp.status_code,
            "title": node.get("title"),
            "text": (node.get("text") or "")[:140],
        }
    )

print(json.dumps({"start": start.status_code, "turns": turns}, ensure_ascii=False, indent=2))
