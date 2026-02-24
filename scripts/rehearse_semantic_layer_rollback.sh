#!/bin/bash

# =========================================
# Semantic Layer Rollback Rehearsal
# -----------------------------------------
# 1. Boot backend (feature flags on) + Paper server
# 2. Capture semantic candidate response
# 3. Restart backend with flags off (server stays up)
# 4. Capture fallback response without semantic layer
# 5. Restore flags, collect logs, and tear everything down
# 6. Archive artefacts under logs/rollback_rehearsal/<timestamp>
#
# The script is intentionally self-contained so it can be
# re-run during release rehearsals without manual steps.
# =========================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
SERVER_DIR="$BACKEND_DIR/server"
AUTO_BUILD_PID_FILE="$REPO_ROOT/auto_build.pid"
AUTO_BUILD_LOG="$REPO_ROOT/logs/auto_build.log"
LOG_BASE="$REPO_ROOT/logs/rollback_rehearsal"
RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
RUN_DIR="$LOG_BASE/$RUN_ID"
BACKEND_PORT=8000
PLAN_ENDPOINT="http://127.0.0.1:${BACKEND_PORT}/intent/plan"
REQUEST_MESSAGE=$'\u653e\u4e00\u4e2a\u7075\u9b42\u706f\u7b52'
MC_RCON_HOST="${MINECRAFT_RCON_HOST:-127.0.0.1}"
MC_RCON_PORT="${MINECRAFT_RCON_PORT:-25575}"
MC_RCON_PASSWORD="${MINECRAFT_RCON_PASSWORD:-drift_rcon_dev}"

mkdir -p "$RUN_DIR"

BACKEND_PID=""
MC_LAUNCH_PID=""
MC_SERVER_PID=""

log() {
    printf '[%s] %s\n' "$(date +"%H:%M:%S")" "$*"
}

wait_for_pid_exit() {
    local target_pid="$1"
    local timeout_seconds="$2"
    local waited=0

    if [ -z "$target_pid" ]; then
        return 0
    fi

    while kill -0 "$target_pid" >/dev/null 2>&1; do
        if [ "$waited" -ge "$timeout_seconds" ]; then
            log "Process $target_pid still running after ${timeout_seconds}s, sending SIGKILL"
            kill -9 "$target_pid" >/dev/null 2>&1 || true
            break
        fi
        sleep 1
        waited=$((waited + 1))
    done
}

ensure_backend_env() {
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        log "Creating backend virtualenv"
        python3 -m venv "$BACKEND_DIR/venv"
    fi
    log "Installing backend dependencies"
    "$BACKEND_DIR/venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
}

wait_for_backend_ready() {
    local attempts=30
    local wait_seconds=2
    for ((i = 1; i <= attempts; i++)); do
        if curl -fsS -m 2 "http://127.0.0.1:${BACKEND_PORT}/" >/dev/null; then
            log "Backend is ready"
            return 0
        fi
        sleep "$wait_seconds"
    done
    log "Backend did not become ready after $((attempts * wait_seconds))s"
    return 1
}

start_backend_phase() {
    local phase="$1"
    local semantic_flag transformer_flag phase_log

    case "$phase" in
        semantic_on)
            semantic_flag=1
            transformer_flag=1
            ;;
        semantic_off)
            semantic_flag=0
            transformer_flag=0
            ;;
        semantic_restore)
            semantic_flag=1
            transformer_flag=1
            ;;
        *)
            log "Unknown backend phase: $phase"
            return 1
            ;;
    esac

    phase_log="$RUN_DIR/backend_${phase}.log"
    log "Starting backend (${phase}) with SEMANTIC_LAYER_ENABLED=${semantic_flag}, TRANSFORMER_PROPOSAL_ENABLED=${transformer_flag}"

    pushd "$BACKEND_DIR" >/dev/null
    nohup env \
        PYTHONUNBUFFERED=1 \
        SEMANTIC_LAYER_ENABLED="$semantic_flag" \
        TRANSFORMER_PROPOSAL_ENABLED="$transformer_flag" \
        "$BACKEND_DIR/venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
        >"$phase_log" 2>&1 &
    BACKEND_PID=$!
    popd >/dev/null

    echo "$BACKEND_PID" >"$RUN_DIR/backend_${phase}.pid"

    wait_for_backend_ready || return 1
    log "Backend (${phase}) started (PID: $BACKEND_PID)"
}

stop_backend() {
    if [ -z "$BACKEND_PID" ]; then
        return 0
    fi
    if kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
        log "Stopping backend (PID: $BACKEND_PID)"
        kill "$BACKEND_PID" >/dev/null 2>&1 || true
        wait_for_pid_exit "$BACKEND_PID" 20
    fi
    BACKEND_PID=""
}

wait_for_mc_ready() {
    local log_file="$SERVER_DIR/logs/latest.log"
    local attempts=80
    local wait_seconds=3

    for ((i = 1; i <= attempts; i++)); do
        if grep -q "Done (" "$log_file" 2>/dev/null; then
            if [ -z "$MC_SERVER_PID" ]; then
                MC_SERVER_PID="$(pgrep -P "$MC_LAUNCH_PID" 2>/dev/null | head -n 1 || true)"
                if [ -z "$MC_SERVER_PID" ]; then
                    MC_SERVER_PID="$(pgrep -f 'paper-.*\\.jar' 2>/dev/null | head -n 1 || true)"
                fi
                if [ -n "$MC_SERVER_PID" ]; then
                    echo "$MC_SERVER_PID" >"$RUN_DIR/mc_server.pid"
                fi
            fi
            log "Minecraft server ready"
            return 0
        fi
        if ! kill -0 "$MC_LAUNCH_PID" >/dev/null 2>&1; then
            log "Minecraft launcher exited unexpectedly"
            return 1
        fi
        sleep "$wait_seconds"
    done
    log "Minecraft server did not report readiness after $((attempts * wait_seconds))s"
    return 1
}

start_minecraft_server() {
    local console_log="$RUN_DIR/mc_console.log"
    log "Starting Minecraft server"
    pushd "$BACKEND_DIR" >/dev/null
    nohup ./start_mc.sh >"$console_log" 2>&1 &
    MC_LAUNCH_PID=$!
    popd >/dev/null

    echo "$MC_LAUNCH_PID" >"$RUN_DIR/mc_launcher.pid"
    wait_for_mc_ready || return 1
}

stop_auto_build() {
    if [ -f "$AUTO_BUILD_PID_FILE" ]; then
        local pid
        pid="$(cat "$AUTO_BUILD_PID_FILE" 2>/dev/null || true)"
        if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
            log "Stopping auto_build watcher (PID: $pid)"
            kill "$pid" >/dev/null 2>&1 || true
            wait_for_pid_exit "$pid" 10
        fi
        rm -f "$AUTO_BUILD_PID_FILE"
    fi
}

stop_minecraft_server() {
    if [ -z "$MC_LAUNCH_PID" ]; then
        stop_auto_build
        return 0
    fi

    resolve_mc_pid() {
        if [ -z "$MC_SERVER_PID" ]; then
            MC_SERVER_PID="$(pgrep -P "$MC_LAUNCH_PID" 2>/dev/null | head -n 1 || true)"
        fi
        if [ -z "$MC_SERVER_PID" ]; then
            MC_SERVER_PID="$(pgrep -f 'paper-.*\\.jar' 2>/dev/null | head -n 1 || true)"
        fi
    }

    if kill -0 "$MC_LAUNCH_PID" >/dev/null 2>&1; then
        log "Stopping Minecraft server via RCON"
        env \
            PYTHONPATH="$BACKEND_DIR" \
            MC_RCON_HOST="$MC_RCON_HOST" \
            MC_RCON_PORT="$MC_RCON_PORT" \
            MC_RCON_PASSWORD="$MC_RCON_PASSWORD" \
            python3 <<'PY'
import os
import time
from app.core.minecraft.rcon_client import RconClient

host = os.environ.get("MC_RCON_HOST", "127.0.0.1")
port = int(os.environ.get("MC_RCON_PORT", "25575"))
password = os.environ.get("MC_RCON_PASSWORD", "drift_rcon_dev")

try:
    client = RconClient(host=host, port=port, password=password, timeout=5.0)
    client.verify()
    client.run(["say [rollback] Shutting down via rehearsal script", "stop"])
except Exception as exc:  # noqa: BLE001
    print(f"Failed to send RCON stop command: {exc}")
    time.sleep(1)
PY
        resolve_mc_pid
        if [ -n "$MC_SERVER_PID" ]; then
            if kill -0 "$MC_SERVER_PID" >/dev/null 2>&1; then
                log "Sending SIGTERM to Minecraft server (PID: $MC_SERVER_PID)"
                kill "$MC_SERVER_PID" >/dev/null 2>&1 || true
                wait_for_pid_exit "$MC_SERVER_PID" 60
            fi
        fi
        wait_for_pid_exit "$MC_LAUNCH_PID" 60
    fi

    MC_LAUNCH_PID=""
    MC_SERVER_PID=""
    stop_auto_build
}

cleanup() {
    set +e
    stop_backend
    stop_minecraft_server
    set -e
}

trap cleanup EXIT

ensure_backend_env
start_backend_phase semantic_on
start_minecraft_server

invoke_plan_phase() {
    local phase="$1"
    local response_file="$RUN_DIR/plan_${phase}.json"
    local metrics_file="$RUN_DIR/metrics_${phase}.txt"
    local summary

    log "Invoking creation plan (${phase})"
    summary=$(env \
        REQUEST_MESSAGE="$REQUEST_MESSAGE" \
        PLAN_ENDPOINT="$PLAN_ENDPOINT" \
        RESPONSE_FILE="$response_file" \
        METRICS_FILE="$metrics_file" \
        python3 <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

message = os.environ["REQUEST_MESSAGE"]
endpoint = os.environ["PLAN_ENDPOINT"]
response_file = os.environ["RESPONSE_FILE"]
metrics_file = os.environ["METRICS_FILE"]

payload = json.dumps({"message": message}).encode("utf-8")
request = urllib.request.Request(
    endpoint,
    data=payload,
    headers={"Content-Type": "application/json"},
)

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

try:
    with opener.open(request, timeout=20) as resp:
        body_bytes = resp.read()
except urllib.error.URLError as exc:  # noqa: BLE001
    raise SystemExit(f"Failed to reach backend: {exc}") from exc

try:
    payload_json = json.loads(body_bytes.decode("utf-8"))
except json.JSONDecodeError as exc:  # noqa: BLE001
    raise SystemExit(f"Backend returned invalid JSON: {exc}") from exc

with open(response_file, "w", encoding="utf-8") as fh:
    json.dump(payload_json, fh, ensure_ascii=False, indent=2)

candidates = payload_json.get("semantic_candidates") or []
layer_hits = 0
for candidate in candidates:
    sources = candidate.get("source") or candidate.get("sources") or []
    if isinstance(sources, (list, tuple, set)) and any(str(item) == "semantic_layer" for item in sources):
        layer_hits += 1

summary = {
    "semantic_candidates": len(candidates),
    "semantic_layer_hits": layer_hits,
    "execution_tier": payload_json.get("execution_tier"),
}

with open(metrics_file, "w", encoding="utf-8") as fh:
    for key, value in summary.items():
        fh.write(f"{key}: {value}\n")

print(json.dumps(summary, ensure_ascii=True))
PY
    )
    log "Plan summary (${phase}): ${summary}"
}

invoke_plan_phase semantic_on

stop_backend
start_backend_phase semantic_off
invoke_plan_phase semantic_off

stop_backend
start_backend_phase semantic_restore
invoke_plan_phase semantic_restore
stop_backend

stop_minecraft_server

if [ -f "$BACKEND_DIR/backend.log" ]; then
    cp "$BACKEND_DIR/backend.log" "$RUN_DIR/backend_full.log"
fi
if [ -f "$AUTO_BUILD_LOG" ]; then
    cp "$AUTO_BUILD_LOG" "$RUN_DIR/auto_build.log"
fi
if [ -f "$SERVER_DIR/logs/latest.log" ]; then
    cp "$SERVER_DIR/logs/latest.log" "$RUN_DIR/mc_latest.log"
fi

{
    printf "Rollback rehearsal ID: %s\n\n" "$RUN_ID"
    for phase in semantic_on semantic_off semantic_restore; do
        metrics_file="$RUN_DIR/metrics_${phase}.txt"
        if [ -f "$metrics_file" ]; then
            printf "[%s]\n" "$phase"
            cat "$metrics_file"
            printf "\n"
        fi
    done
} >"$RUN_DIR/summary.txt"

log "Rollback rehearsal artefacts stored in: $RUN_DIR"
log "Files captured:"
for artifact in \
    plan_semantic_on.json \
    plan_semantic_off.json \
    plan_semantic_restore.json \
    metrics_semantic_on.txt \
    metrics_semantic_off.txt \
    metrics_semantic_restore.txt \
    backend_semantic_on.log \
    backend_semantic_off.log \
    backend_semantic_restore.log \
    backend_full.log \
    mc_console.log \
    mc_latest.log \
    auto_build.log \
    summary.txt; do
    if [ -f "$RUN_DIR/$artifact" ]; then
        printf '  - %s\n' "$artifact"
    fi
done

ls "$RUN_DIR"
