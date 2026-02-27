#!/usr/bin/env bash
set -euo pipefail

# DriftSystem one-click server ops
# Flow: check -> optional git pull -> build/deploy plugin -> stop/clean -> restart -> verify

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_DIR="${PLUGIN_DIR:-$ROOT_DIR/system/mc_plugin}"
BACKEND_URL="${BACKEND_URL:-https://driftsystem-production.up.railway.app}"
DO_GIT_PULL="${DO_GIT_PULL:-1}"
BUILD_PLUGIN="${BUILD_PLUGIN:-1}"
RESTART_MC="${RESTART_MC:-1}"
RESTART_BACKEND_LOCAL="${RESTART_BACKEND_LOCAL:-0}"
RUN_STORY_SMOKE="${RUN_STORY_SMOKE:-1}"
STRICT_STORY_SMOKE="${STRICT_STORY_SMOKE:-1}"

if [[ -n "${MC_DIR:-}" ]]; then
  SERVER_DIR="$MC_DIR"
elif [[ -d "$ROOT_DIR/backend/server" ]]; then
  SERVER_DIR="$ROOT_DIR/backend/server"
elif [[ -d "$ROOT_DIR/server" ]]; then
  SERVER_DIR="$ROOT_DIR/server"
else
  SERVER_DIR="/mc"
fi

PLUGINS_DIR="${PLUGINS_DIR:-$SERVER_DIR/plugins}"
PLUGIN_DEST_JAR="${PLUGIN_DEST_JAR:-$PLUGINS_DIR/DriftSystem.jar}"
RUNTIME_PLUGIN_CFG="${RUNTIME_PLUGIN_CFG:-$PLUGINS_DIR/DriftSystem/config.yml}"
LOCAL_BACKEND_DIR="${LOCAL_BACKEND_DIR:-$ROOT_DIR/backend}"
LOCAL_BACKEND_PORT="${LOCAL_BACKEND_PORT:-8000}"
SMOKE_SCRIPT="${SMOKE_SCRIPT:-$ROOT_DIR/scripts/smoke_story_scene.sh}"
SMOKE_PLAYER_ID="${SMOKE_PLAYER_ID:-ops_smoke_runner}"
SMOKE_TITLE="${SMOKE_TITLE:-运维冒烟-剧情场景}"
SMOKE_TEXT="${SMOKE_TEXT:-请导入剧情：夜晚工坊、向导NPC、两盏灯}"

print_step() { echo -e "\n${BLUE}==> $1${NC}"; }
print_ok() { echo -e "${GREEN}✓ $1${NC}"; }
print_warn() { echo -e "${YELLOW}! $1${NC}"; }
print_err() { echo -e "${RED}✗ $1${NC}"; }

need_cmd() {
  local c="$1"
  if ! command -v "$c" >/dev/null 2>&1; then
    print_err "缺少命令: $c"
    exit 1
  fi
}

kill_port_listeners() {
  local port="$1"
  local pids
  pids="$(lsof -ti :"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    print_warn "停止端口 $port 监听进程: $pids"
    kill -9 $pids 2>/dev/null || true
  fi
}

stop_mc_processes() {
  local pids
  pids="$(pgrep -f 'paper.*jar|minecraft_server.*jar' || true)"
  if [[ -n "$pids" ]]; then
    print_warn "停止 Minecraft 进程: $pids"
    kill -15 $pids 2>/dev/null || true
    sleep 3
    pids="$(pgrep -f 'paper.*jar|minecraft_server.*jar' || true)"
    if [[ -n "$pids" ]]; then
      print_warn "强制停止残留 Minecraft 进程: $pids"
      kill -9 $pids 2>/dev/null || true
    fi
  fi
}

clean_session_locks() {
  local worlds=(
    "$SERVER_DIR/world/session.lock"
    "$SERVER_DIR/world_nether/session.lock"
    "$SERVER_DIR/world_the_end/session.lock"
    "$SERVER_DIR/.world/session.lock"
  )
  for f in "${worlds[@]}"; do
    [[ -f "$f" ]] && rm -f "$f"
  done
  print_ok "session.lock 清理完成"
}

update_runtime_backend_url() {
  if [[ -f "$RUNTIME_PLUGIN_CFG" ]]; then
    if grep -q '^backend_url:' "$RUNTIME_PLUGIN_CFG"; then
      sed -i.bak "s|^backend_url:.*|backend_url: \"$BACKEND_URL\"|" "$RUNTIME_PLUGIN_CFG"
    else
      printf '\nbackend_url: "%s"\n' "$BACKEND_URL" >> "$RUNTIME_PLUGIN_CFG"
    fi
    print_ok "运行时插件配置已指向: $BACKEND_URL"
  else
    print_warn "未找到运行时插件配置: ${RUNTIME_PLUGIN_CFG}（将在插件首次启动后生成）"
  fi
}

restart_mc_service_or_process() {
  if [[ "$RESTART_MC" != "1" ]]; then
    print_warn "已跳过 MC 重启（RESTART_MC=0）"
    return
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q '^minecraft\.service'; then
    systemctl daemon-reload || true
    systemctl restart minecraft.service
    print_ok "minecraft.service 已重启"
    return
  fi

  if [[ -x "$SERVER_DIR/start.sh" ]]; then
    (cd "$SERVER_DIR" && nohup ./start.sh >/tmp/start_mc.out 2>&1 &)
    print_ok "已通过 ${SERVER_DIR}/start.sh 启动 MC"
    return
  fi

  local paper
  paper="$(find "$SERVER_DIR" -maxdepth 1 -type f \( -name 'paper*.jar' -o -name 'minecraft_server*.jar' \) | head -n 1)"
  if [[ -n "$paper" ]]; then
    (cd "$SERVER_DIR" && nohup java -Xms2G -Xmx4G -jar "$(basename "$paper")" nogui >/tmp/start_mc.out 2>&1 &)
    print_ok "已直接启动: $(basename "$paper")"
  else
    print_err "未找到可启动的 MC jar（${SERVER_DIR}）"
    exit 1
  fi
}

restart_local_backend_if_requested() {
  if [[ "$RESTART_BACKEND_LOCAL" != "1" ]]; then
    return
  fi

  if [[ ! -d "$LOCAL_BACKEND_DIR" ]]; then
    print_warn "本地 backend 目录不存在，跳过本地 backend 重启"
    return
  fi

  kill_port_listeners "$LOCAL_BACKEND_PORT"

  local py_cmd
  if [[ -x "$LOCAL_BACKEND_DIR/venv/bin/python" ]]; then
    py_cmd="$LOCAL_BACKEND_DIR/venv/bin/python"
  elif [[ -x "$LOCAL_BACKEND_DIR/.venv/bin/python" ]]; then
    py_cmd="$LOCAL_BACKEND_DIR/.venv/bin/python"
  else
    py_cmd="python3"
  fi

  (cd "$LOCAL_BACKEND_DIR" && nohup "$py_cmd" -m uvicorn app.main:app --host 0.0.0.0 --port "$LOCAL_BACKEND_PORT" >/tmp/drift_backend.out 2>&1 &)
  print_ok "本地 backend 已重启: 0.0.0.0:$LOCAL_BACKEND_PORT"
}

health_checks() {
  print_step "健康检查"

  if curl -fsS --max-time 12 "$BACKEND_URL/ai/quota-status" >/tmp/drift_quota_check.json 2>/dev/null; then
    print_ok "后端可达: $BACKEND_URL"
  else
    print_err "后端不可达: $BACKEND_URL"
    return 1
  fi

  if lsof -Pi :25565 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_ok "MC 端口 25565 正在监听"
  else
    print_warn "MC 端口 25565 尚未监听（可能还在启动）"
  fi
}

run_story_smoke_if_requested() {
  if [[ "$RUN_STORY_SMOKE" != "1" ]]; then
    print_warn "已跳过剧情场景冒烟（RUN_STORY_SMOKE=0）"
    return
  fi

  print_step "剧情场景冒烟验证"

  if [[ ! -x "$SMOKE_SCRIPT" ]]; then
    if [[ -f "$SMOKE_SCRIPT" ]]; then
      chmod +x "$SMOKE_SCRIPT"
    else
      if [[ "$STRICT_STORY_SMOKE" == "1" ]]; then
        print_err "未找到冒烟脚本: $SMOKE_SCRIPT"
        exit 1
      fi
      print_warn "未找到冒烟脚本，已跳过: $SMOKE_SCRIPT"
      return
    fi
  fi

  if BASE_URL="$BACKEND_URL" \
     PLAYER_ID="$SMOKE_PLAYER_ID" \
     TITLE="$SMOKE_TITLE" \
     TEXT="$SMOKE_TEXT" \
     "$SMOKE_SCRIPT"; then
    print_ok "剧情场景冒烟通过"
  else
    if [[ "$STRICT_STORY_SMOKE" == "1" ]]; then
      print_err "剧情场景冒烟失败（STRICT_STORY_SMOKE=1）"
      exit 1
    fi
    print_warn "剧情场景冒烟失败，但已放行（STRICT_STORY_SMOKE=0）"
  fi
}

main() {
  print_step "环境检查"
  need_cmd bash
  need_cmd curl
  need_cmd git
  need_cmd sed
  need_cmd lsof

  [[ "$BUILD_PLUGIN" == "1" ]] && need_cmd mvn

  print_ok "ROOT_DIR=$ROOT_DIR"
  print_ok "SERVER_DIR=$SERVER_DIR"
  print_ok "BACKEND_URL=$BACKEND_URL"

  if [[ "$DO_GIT_PULL" == "1" ]]; then
    print_step "更新代码"
    (cd "$ROOT_DIR" && git pull --ff-only)
    print_ok "代码已更新"
  else
    print_warn "已跳过 git pull（DO_GIT_PULL=0）"
  fi

  if [[ "$BUILD_PLUGIN" == "1" ]]; then
    print_step "构建插件"
    (cd "$PLUGIN_DIR" && ./build.sh)
    print_ok "插件构建完成"
  else
    print_warn "已跳过插件构建（BUILD_PLUGIN=0）"
  fi

  print_step "停止旧服务并清理"
  stop_mc_processes
  kill_port_listeners 25565
  kill_port_listeners 25575
  clean_session_locks

  print_step "部署插件与配置"
  mkdir -p "$PLUGINS_DIR"
  if [[ -f "$PLUGIN_DIR/target/mc_plugin-1.0-SNAPSHOT.jar" ]]; then
    cp "$PLUGIN_DIR/target/mc_plugin-1.0-SNAPSHOT.jar" "$PLUGIN_DEST_JAR"
    print_ok "插件已部署: $PLUGIN_DEST_JAR"
  else
    print_err "未找到插件产物: ${PLUGIN_DIR}/target/mc_plugin-1.0-SNAPSHOT.jar"
    exit 1
  fi
  update_runtime_backend_url

  print_step "重启服务"
  restart_local_backend_if_requested
  restart_mc_service_or_process

  sleep 4
  health_checks
  run_story_smoke_if_requested

  echo
  print_ok "一键运维完成"
  echo "- 后端地址: $BACKEND_URL"
  echo "- MC 目录: $SERVER_DIR"
  echo "- 插件配置: $RUNTIME_PLUGIN_CFG"
}

main "$@"
