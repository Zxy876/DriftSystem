from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = [
    "selected_root",
    "candidate_scores",
    "selected_children",
    "blocked",
    "reasons",
]

ANCHOR = {"world": "world", "x": 12.0, "y": 65.0, "z": -3.0}

SCENARIOS = {
    "camp": {
        "expected_root": "camp",
        "items": [("oak_log", 2), ("torch", 1), ("raw_porkchop", 1)],
        "scene_theme": "语义探针营地",
    },
    "forge": {
        "expected_root": "forge",
        "items": [("iron_ingot", 2), ("stone", 2), ("campfire", 1)],
        "scene_theme": "语义探针锻造",
    },
    "village": {
        "expected_root": "village",
        "items": [("bread", 3), ("emerald", 2), ("water_bucket", 1), ("oak_log", 1)],
        "scene_theme": "语义探针村落",
    },
}


def _request(base_url: str, method: str, path: str, payload: dict[str, Any] | None, timeout: int) -> tuple[int, dict[str, Any]]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return int(response.status), parsed if isinstance(parsed, dict) else {"raw": parsed}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw}
        return int(exc.code), parsed if isinstance(parsed, dict) else {"raw": parsed}


def _post(base_url: str, path: str, payload: dict[str, Any], timeout: int) -> tuple[int, dict[str, Any]]:
    return _request(base_url, "POST", path, payload, timeout)


def _get(base_url: str, path: str, timeout: int) -> tuple[int, dict[str, Any]]:
    return _request(base_url, "GET", path, None, timeout)


def _scene_signature(scene_generation: dict[str, Any]) -> str:
    signature_payload = {
        "selected_root": scene_generation.get("selected_root"),
        "candidate_scores": scene_generation.get("candidate_scores")
        if isinstance(scene_generation.get("candidate_scores"), list)
        else [],
        "selected_children": scene_generation.get("selected_children")
        if isinstance(scene_generation.get("selected_children"), list)
        else [],
        "blocked": scene_generation.get("blocked") if isinstance(scene_generation.get("blocked"), list) else [],
        "reasons": scene_generation.get("reasons") if isinstance(scene_generation.get("reasons"), dict) else {},
    }
    return json.dumps(signature_payload, ensure_ascii=False, sort_keys=True)


def run_probe(base_url: str, runs_per_scenario: int, timeout: int) -> dict[str, Any]:
    all_results: dict[str, Any] = {}
    failed_scenarios: list[str] = []

    for scenario_name, config in SCENARIOS.items():
        runs: list[dict[str, Any]] = []
        for run_index in range(runs_per_scenario):
            player_id = f"p6b_{scenario_name}_{int(time.time())}_{run_index}_{uuid.uuid4().hex[:6]}"
            level_id = f"p6b_probe_{scenario_name}_{uuid.uuid4().hex[:8]}"

            start_status, start_resp = _post(base_url, "/world/story/start", {"player_id": player_id}, timeout)

            collect_ok = True
            collect_events: list[dict[str, Any]] = []
            for item_type, amount in config["items"]:
                collect_status, collect_resp = _post(
                    base_url,
                    "/world/story/rule-event",
                    {
                        "player_id": player_id,
                        "event_type": "collect",
                        "payload": {
                            "item_type": item_type,
                            "amount": amount,
                            "location": {"world": "world", "x": 12, "y": 65, "z": -3},
                        },
                    },
                    timeout,
                )
                collect_events.append(
                    {
                        "item": item_type,
                        "amount": amount,
                        "status": collect_status,
                        "resp_status": collect_resp.get("status"),
                    }
                )
                if collect_status != 200 or collect_resp.get("status") != "ok":
                    collect_ok = False

            inject_status, inject_resp = _post(
                base_url,
                "/story/inject",
                {
                    "level_id": level_id,
                    "title": f"P6B runtime probe {scenario_name}",
                    "text": f"P6B runtime probe {scenario_name}",
                    "player_id": player_id,
                    "scene_theme": config["scene_theme"],
                    "player_position": ANCHOR,
                },
                timeout,
            )

            encoded_player = urllib.parse.quote(player_id)
            encoded_level = urllib.parse.quote(level_id)
            load_status, load_resp = _post(
                base_url,
                f"/story/load/{encoded_player}/{encoded_level}",
                {},
                timeout,
            )

            debug_status, debug_resp = _get(base_url, f"/world/story/{encoded_player}/debug/tasks", timeout)

            scene_generation = debug_resp.get("scene_generation") if isinstance(debug_resp, dict) else {}
            if not isinstance(scene_generation, dict):
                scene_generation = {}

            present_fields = {field: (field in scene_generation) for field in REQUIRED_FIELDS}
            fields_visible = all(present_fields.values())
            selected_root = str(scene_generation.get("selected_root") or "")

            candidate_scores = scene_generation.get("candidate_scores") if isinstance(scene_generation.get("candidate_scores"), list) else []
            selected_children = scene_generation.get("selected_children") if isinstance(scene_generation.get("selected_children"), list) else []
            blocked = scene_generation.get("blocked") if isinstance(scene_generation.get("blocked"), list) else []
            reasons = scene_generation.get("reasons") if isinstance(scene_generation.get("reasons"), dict) else {}

            run_record = {
                "player_id": player_id,
                "level_id": level_id,
                "start_status": start_status,
                "start_resp_status": start_resp.get("status"),
                "collect_ok": collect_ok,
                "collect_events": collect_events,
                "inject_status": inject_status,
                "inject_resp_status": inject_resp.get("status"),
                "load_status": load_status,
                "load_resp_status": load_resp.get("status"),
                "debug_status": debug_status,
                "debug_resp_status": debug_resp.get("status"),
                "fields_visible": fields_visible,
                "present_fields": present_fields,
                "selected_root": selected_root,
                "top_candidates": candidate_scores[:3],
                "selected_children": selected_children,
                "blocked_count": len(blocked),
                "reasons": reasons,
                "signature": _scene_signature(scene_generation),
            }
            runs.append(run_record)

        roots = [str(run.get("selected_root") or "") for run in runs]
        signatures = [str(run.get("signature") or "") for run in runs]

        deterministic = len(set(signatures)) == 1
        visibility_ok = all(bool(run.get("fields_visible")) for run in runs)
        root_ok = all(root == config["expected_root"] for root in roots)
        flow_ok = all(
            bool(run.get("collect_ok"))
            and run.get("inject_status") == 200
            and run.get("inject_resp_status") in {"ok", "success"}
            and run.get("load_status") == 200
            and run.get("load_resp_status") == "ok"
            and run.get("debug_status") == 200
            for run in runs
        )

        scenario_pass = deterministic and visibility_ok and root_ok and flow_ok
        if not scenario_pass:
            failed_scenarios.append(scenario_name)

        all_results[scenario_name] = {
            "expected_root": config["expected_root"],
            "roots": roots,
            "deterministic": deterministic,
            "visibility_ok": visibility_ok,
            "root_ok": root_ok,
            "flow_ok": flow_ok,
            "pass": scenario_pass,
            "sample_top_candidates": runs[0].get("top_candidates") if runs else [],
            "sample_selected_children": runs[0].get("selected_children") if runs else [],
            "sample_reasons": runs[0].get("reasons") if runs else {},
            "sample_blocked_count": runs[0].get("blocked_count") if runs else 0,
            "runs": runs,
        }

    cross_roots = {name: all_results[name].get("roots", [""])[0] for name in SCENARIOS.keys()}
    root_diversity_ok = len(set(cross_roots.values())) == len(SCENARIOS)

    return {
        "timestamp": int(time.time()),
        "base_url": base_url,
        "required_fields": list(REQUIRED_FIELDS),
        "runs_per_scenario": runs_per_scenario,
        "cross_scenario_root_diversity_ok": root_diversity_ok,
        "cross_scenario_roots": cross_roots,
        "overall_pass": len(failed_scenarios) == 0 and root_diversity_ok,
        "failed_scenarios": failed_scenarios,
        "results": all_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-B runtime probe for scoring visibility and deterministic branches")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--runs", type=int, default=3, help="Runs per scenario")
    parser.add_argument("--timeout", type=int, default=45, help="Request timeout in seconds")
    parser.add_argument(
        "--output-dir",
        default="logs/runtime_probe",
        help="Directory for output json report",
    )
    args = parser.parse_args()

    report = run_probe(base_url=str(args.base_url).rstrip("/"), runs_per_scenario=max(1, int(args.runs)), timeout=max(5, int(args.timeout)))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / f"p6b_runtime_probe_{report['timestamp']}.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"report_file={report_file}")
    print(f"overall_pass={report.get('overall_pass')}")
    print(f"cross_scenario_root_diversity_ok={report.get('cross_scenario_root_diversity_ok')}")
    for scenario_name in SCENARIOS.keys():
        scenario = report.get("results", {}).get(scenario_name, {})
        print(
            f"scenario={scenario_name} pass={scenario.get('pass')} roots={scenario.get('roots')} "
            f"deterministic={scenario.get('deterministic')} visibility_ok={scenario.get('visibility_ok')}"
        )

    return 0 if bool(report.get("overall_pass")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
