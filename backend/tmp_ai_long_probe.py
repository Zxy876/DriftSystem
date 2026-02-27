import json
import statistics
import time
from collections import Counter

import requests

BASE = "https://driftsystem-production.up.railway.app"


def summarize(lat):
    if not lat:
        return {"min": None, "p50": None, "p95": None, "max": None, "avg": None}
    ordered = sorted(lat)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    return {
        "min": round(min(lat), 1),
        "p50": round(statistics.median(lat), 1),
        "p95": round(p95, 1),
        "max": round(max(lat), 1),
        "avg": round(sum(lat) / len(lat), 1),
    }


def run_probe(endpoint, payload_builder, samples, timeout):
    lat = []
    statuses = Counter()
    errors = Counter()
    for i in range(samples):
        payload = payload_builder(i)
        t0 = time.time()
        try:
            r = requests.post(f"{BASE}{endpoint}", json=payload, timeout=timeout)
            lat.append((time.time() - t0) * 1000)
            statuses[str(r.status_code)] += 1
        except Exception as exc:
            errors[exc.__class__.__name__] += 1
    return {
        "endpoint": endpoint,
        "samples": samples,
        "status_counts": dict(statuses),
        "error_counts": dict(errors),
        "latency_ms": summarize(lat),
    }


intent = run_probe(
    endpoint="/ai/intent",
    payload_builder=lambda i: {
        "player_id": f"long_probe_intent_{i % 3 + 1}",
        "text": "我想导入和爷爷在院子里修风筝的回忆场景并和AI互动",
        "mode": "shared",
    },
    samples=60,
    timeout=15,
)

inject = run_probe(
    endpoint="/story/inject",
    payload_builder=lambda i: {
        "level_id": f"long_probe_inject_{int(time.time())}_{i}",
        "player_id": f"long_probe_mem_{i % 3 + 1}",
        "title": f"长样本诊断_{i}",
        "text": "请导入剧情：我和爷爷在院子里修风筝",
        "execute_confirm": False,
    },
    samples=30,
    timeout=25,
)

print(json.dumps({"base_url": BASE, "intent": intent, "inject": inject}, ensure_ascii=False, indent=2))
