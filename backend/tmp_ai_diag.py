import json
import statistics
import time
from collections import Counter

import requests

BASE = "https://driftsystem-production.up.railway.app"


def summarize_latency(latencies):
    if not latencies:
        return {
            "min": None,
            "p50": None,
            "p95": None,
            "max": None,
            "avg": None,
        }
    ordered = sorted(latencies)
    p95_index = max(0, int(len(ordered) * 0.95) - 1)
    return {
        "min": round(min(latencies), 1),
        "p50": round(statistics.median(latencies), 1),
        "p95": round(ordered[p95_index], 1),
        "max": round(max(latencies), 1),
        "avg": round(sum(latencies) / len(latencies), 1),
    }


def probe_intent(samples=20, timeout=20):
    url = f"{BASE}/ai/intent"
    latencies = []
    status_counts = Counter()
    errors = Counter()

    for i in range(samples):
        payload = {
            "player_id": f"probe_intent_{i % 3 + 1}",
            "text": "我想导入和爷爷一起在老院子修风筝的回忆场景",
            "mode": "shared",
        }
        started = time.time()
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            latencies.append((time.time() - started) * 1000)
            status_counts[str(response.status_code)] += 1
        except Exception as exc:
            errors[exc.__class__.__name__] += 1

    return {
        "endpoint": "/ai/intent",
        "samples": samples,
        "status_counts": dict(status_counts),
        "error_counts": dict(errors),
        "latency_ms": summarize_latency(latencies),
    }


def probe_inject(samples=12, timeout=60):
    url = f"{BASE}/story/inject"
    latencies = []
    status_counts = Counter()
    scene_status_counts = Counter()
    errors = Counter()

    story_texts = [
        "请导入剧情：我和爷爷在老院子修风筝，黄昏有桂花香",
        "请导入剧情：爷爷带我在河边钓鱼，清晨有薄雾和鸟叫",
        "请导入剧情：我和爷爷在旧书房整理相册，窗外下着小雨",
    ]

    for i in range(samples):
        payload = {
            "level_id": f"probe_inject_{int(time.time())}_{i}",
            "player_id": f"probe_mem_{i % 3 + 1}",
            "title": f"诊断记忆场景_{i}",
            "text": story_texts[i % 3],
            "execute_confirm": False,
        }
        started = time.time()
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            latencies.append((time.time() - started) * 1000)
            status_counts[str(response.status_code)] += 1
            if response.headers.get("content-type", "").startswith("application/json"):
                body = response.json()
                scene_status = body.get("scene_status")
                if scene_status is not None:
                    scene_status_counts[str(scene_status)] += 1
        except Exception as exc:
            errors[exc.__class__.__name__] += 1

    return {
        "endpoint": "/story/inject",
        "samples": samples,
        "status_counts": dict(status_counts),
        "scene_status_counts": dict(scene_status_counts),
        "error_counts": dict(errors),
        "latency_ms": summarize_latency(latencies),
    }


def probe_quota(timeout=15):
    url = f"{BASE}/ai/quota-status"
    started = time.time()
    try:
        response = requests.get(url, timeout=timeout)
        latency = (time.time() - started) * 1000
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "endpoint": "/ai/quota-status",
            "status": response.status_code,
            "latency_ms": round(latency, 1),
            "body": body,
        }
    except Exception as exc:
        return {
            "endpoint": "/ai/quota-status",
            "status": "error",
            "error": exc.__class__.__name__,
        }


if __name__ == "__main__":
    result = {
        "timestamp": int(time.time()),
        "base_url": BASE,
        "quota": probe_quota(),
        "intent_probe": probe_intent(),
        "inject_probe": probe_inject(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
