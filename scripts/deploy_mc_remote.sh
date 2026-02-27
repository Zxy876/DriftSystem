#!/usr/bin/env bash
set -euo pipefail

# Deploy DriftSystem plugin to a remote MC-only server (backend on Railway)
# Usage:
#   scripts/deploy_mc_remote.sh -h <host> [-u ubuntu] [-p 22] [-k ~/.ssh/key] [--backend-url <url>] [--skip-build]

HOST=""
USER_NAME="ubuntu"
PORT="22"
SSH_KEY=""
BACKEND_URL="https://driftsystem-production.up.railway.app"
SKIP_BUILD="0"
RUN_STORY_SMOKE="1"
STRICT_STORY_SMOKE="1"
SMOKE_PLAYER_ID="remote_deploy_smoke"
SMOKE_TITLE="远程部署冒烟-剧情场景"
SMOKE_TEXT="请导入剧情：夜晚广场、向导NPC、两盏灯"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_DIR="$ROOT_DIR/system/mc_plugin"
PLUGIN_JAR="$PLUGIN_DIR/target/mc_plugin-1.0-SNAPSHOT.jar"
SMOKE_SCRIPT="$ROOT_DIR/scripts/smoke_story_scene.sh"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
  cat <<'USAGE'
Deploy DriftSystem plugin to remote MC server.

Required:
  -h, --host           Remote host or IP

Optional:
  -u, --user           SSH user (default: ubuntu)
  -p, --port           SSH port (default: 22)
  -k, --key            SSH private key path
      --backend-url    Backend URL written into /mc/plugins/DriftSystem/config.yml
      --skip-build     Skip local Maven build and reuse existing jar
      --skip-smoke     Skip post-deploy story scene smoke test
      --non-strict-smoke  Smoke failure will not break deploy flow

Example:
  scripts/deploy_mc_remote.sh -h 1.2.3.4 -u ubuntu --backend-url https://driftsystem-production.up.railway.app
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--host)
      HOST="$2"; shift 2 ;;
    -u|--user)
      USER_NAME="$2"; shift 2 ;;
    -p|--port)
      PORT="$2"; shift 2 ;;
    -k|--key)
      SSH_KEY="$2"; shift 2 ;;
    --backend-url)
      BACKEND_URL="$2"; shift 2 ;;
    --skip-build)
      SKIP_BUILD="1"; shift ;;
    --skip-smoke)
      RUN_STORY_SMOKE="0"; shift ;;
    --non-strict-smoke)
      STRICT_STORY_SMOKE="0"; shift ;;
    --help|-help|-?)
      usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ -z "$HOST" ]]; then
  echo "Missing --host" >&2
  usage
  exit 1
fi

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1" >&2; exit 1; }
}

print_step() { echo -e "\n${BLUE}==> $1${NC}"; }
print_ok() { echo -e "${GREEN}✓ $1${NC}"; }
print_warn() { echo -e "${YELLOW}! $1${NC}"; }
print_err() { echo -e "${RED}✗ $1${NC}"; }

need_cmd ssh
need_cmd scp
need_cmd bash

SSH_OPTS=(-p "$PORT" -o StrictHostKeyChecking=accept-new)
SCP_OPTS=(-P "$PORT" -o StrictHostKeyChecking=accept-new)
if [[ -n "$SSH_KEY" ]]; then
  SSH_OPTS+=(-i "$SSH_KEY")
  SCP_OPTS+=(-i "$SSH_KEY")
fi

if [[ "$SKIP_BUILD" != "1" ]]; then
  print_step "本地构建插件"
  need_cmd mvn
  (cd "$PLUGIN_DIR" && ./build.sh)
  print_ok "构建完成"
else
  print_warn "已跳过构建"
fi

if [[ ! -f "$PLUGIN_JAR" ]]; then
  print_err "插件产物不存在: $PLUGIN_JAR"
  exit 1
fi

print_step "上传插件到云服"
scp "${SCP_OPTS[@]}" "$PLUGIN_JAR" "$USER_NAME@$HOST:/tmp/DriftSystem.jar"
print_ok "已上传 /tmp/DriftSystem.jar"

print_step "云服停服、部署、重启、验活"
ssh "${SSH_OPTS[@]}" "$USER_NAME@$HOST" BACKEND_URL="$BACKEND_URL" 'bash -s' <<'REMOTE'
set -euo pipefail

MC_DIR="/mc"
PLUGIN_JAR_SRC="/tmp/DriftSystem.jar"
PLUGIN_JAR_DEST="$MC_DIR/plugins/DriftSystem.jar"
CFG_DIR="$MC_DIR/plugins/DriftSystem"
CFG_FILE="$CFG_DIR/config.yml"

mkdir -p "$MC_DIR/plugins" "$CFG_DIR"

echo "[remote] stop mc"
pkill -f 'paper.*jar|minecraft_server.*jar' 2>/dev/null || true
sleep 2
pkill -9 -f 'paper.*jar|minecraft_server.*jar' 2>/dev/null || true

if command -v lsof >/dev/null 2>&1; then
  pids_25565="$(lsof -ti :25565 2>/dev/null || true)"
  if [[ -n "$pids_25565" ]]; then
    echo "$pids_25565" | xargs -r kill -9
  fi

  pids_25575="$(lsof -ti :25575 2>/dev/null || true)"
  if [[ -n "$pids_25575" ]]; then
    echo "$pids_25575" | xargs -r kill -9
  fi
fi

rm -f "$MC_DIR/world/session.lock" \
      "$MC_DIR/world_nether/session.lock" \
      "$MC_DIR/world_the_end/session.lock" \
      "$MC_DIR/.world/session.lock" 2>/dev/null || true

echo "[remote] deploy plugin"
cp -f "$PLUGIN_JAR_SRC" "$PLUGIN_JAR_DEST"

if [[ -f "$CFG_FILE" ]]; then
  if grep -q '^backend_url:' "$CFG_FILE"; then
    sed -i "s|^backend_url:.*|backend_url: \"$BACKEND_URL\"|" "$CFG_FILE"
  else
    printf '\nbackend_url: "%s"\n' "$BACKEND_URL" >> "$CFG_FILE"
  fi
else
  cat > "$CFG_FILE" <<CFG
backend_url: "$BACKEND_URL"
system:
  debug: false
world:
  allow_story_creation: true
CFG
fi

echo "[remote] restart mc"
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q '^minecraft\.service'; then
  systemctl restart minecraft.service
else
  if [[ -x "$MC_DIR/start.sh" ]]; then
    nohup "$MC_DIR/start.sh" >/tmp/start_mc.out 2>&1 &
  else
    JAR="$(find "$MC_DIR" -maxdepth 1 -type f \( -name 'paper*.jar' -o -name 'minecraft_server*.jar' \) | head -n1)"
    [[ -n "$JAR" ]] || { echo "No MC jar found in /mc"; exit 1; }
    nohup java -Xms2G -Xmx4G -jar "$JAR" nogui >/tmp/start_mc.out 2>&1 &
  fi
fi

sleep 5

if curl -fsS --max-time 12 "$BACKEND_URL/ai/quota-status" >/tmp/drift_quota_check.json 2>/dev/null; then
  echo "[remote] backend reachable"
else
  echo "[remote] backend unreachable: $BACKEND_URL"
fi

if command -v lsof >/dev/null 2>&1 && lsof -Pi :25565 -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[remote] mc port 25565 listening"
else
  echo "[remote] mc port 25565 not listening yet"
fi

echo "[remote] done"
REMOTE

run_story_smoke_after_deploy() {
  if [[ "$RUN_STORY_SMOKE" != "1" ]]; then
    print_warn "已跳过部署后冒烟（--skip-smoke）"
    return
  fi

  print_step "执行部署后剧情场景冒烟"
  if [[ ! -x "$SMOKE_SCRIPT" ]]; then
    if [[ -f "$SMOKE_SCRIPT" ]]; then
      chmod +x "$SMOKE_SCRIPT"
    else
      if [[ "$STRICT_STORY_SMOKE" == "1" ]]; then
        print_err "未找到冒烟脚本: $SMOKE_SCRIPT"
        exit 1
      fi
      print_warn "未找到冒烟脚本，已放行"
      return
    fi
  fi

  if BASE_URL="$BACKEND_URL" \
     PLAYER_ID="$SMOKE_PLAYER_ID" \
     TITLE="$SMOKE_TITLE" \
     TEXT="$SMOKE_TEXT" \
     REQUIRE_SCENE_STATUS_OK=1 \
     "$SMOKE_SCRIPT"; then
    print_ok "部署后剧情场景冒烟通过"
  else
    if [[ "$STRICT_STORY_SMOKE" == "1" ]]; then
      print_err "部署后剧情场景冒烟失败"
      exit 1
    fi
    print_warn "部署后剧情场景冒烟失败，但已放行（--non-strict-smoke）"
  fi
}

run_story_smoke_after_deploy

print_ok "远程部署流程执行完毕"
echo "Host: $HOST"
echo "Backend: $BACKEND_URL"
