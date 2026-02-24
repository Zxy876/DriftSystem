#!/bin/bash

echo "=============================="
echo "🎮 启动 DriftSystem MC 服务端"
echo "=============================="

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$ROOT_DIR/.." && pwd)"
SERVER_DIR="$ROOT_DIR/server"
AUTO_BUILD_SCRIPT="$PROJECT_DIR/tools/auto_build.py"
AUTO_BUILD_LOG="$PROJECT_DIR/logs/auto_build.log"
AUTO_BUILD_PID="$PROJECT_DIR/auto_build.pid"

# Bot auto-join settings
AUTO_BOT=${AUTO_BOT:-1}
BOT_TASK_FILE=${BOT_TASK_FILE:-/tmp/film_task.json}
BOT_HOST=${BOT_HOST:-127.0.0.1}
BOT_PORT=${BOT_PORT:-25565}
BOT_USERNAME=${BOT_USERNAME:-crew_builder_01}
BOT_VERSION=${BOT_VERSION:-1.20.1}
BOT_TASK_LEVEL=${BOT_TASK_LEVEL:-staging_setdress_001}
BOT_STAY_ONLINE=${BOT_STAY_ONLINE:-0}

cd "$SERVER_DIR"

# 清理上一轮遗留的 PID 和世界锁文件，避免 SessionLock 异常
if [ -f "server.pid" ]; then
    OLD_PID=$(cat server.pid 2>/dev/null)
    if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" >/dev/null 2>&1; then
        echo "❌ 检测到已有运行中的 MC 服务 (PID: $OLD_PID)，请先停止它。"
        exit 1
    fi
    rm -f server.pid
fi

find world world_nether world_the_end -maxdepth 1 -name session.lock -exec rm -f {} + 2>/dev/null

create_default_bot_task() {
    if [ -f "$BOT_TASK_FILE" ]; then
        return
    fi
    cat > "$BOT_TASK_FILE" <<'EOF'
{
  "task_id": "film-session-001",
  "level_id": "BOT_TASK_LEVEL_PLACEHOLDER",
  "assigned_to": "BOT_USERNAME_PLACEHOLDER",
  "summary": "Camera bot idle at staging set",
  "actions": [
    {
      "action": "travel",
      "position": [1, 64, 1],
      "note": "Move to spawn area for filming"
    }
  ]
}
EOF
    # replace placeholders
    python3 - "$BOT_TASK_LEVEL" "$BOT_USERNAME" "$BOT_TASK_FILE" <<'PY'
import json, sys, pathlib
level_id, username, path = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
data = json.loads(path.read_text())
data["level_id"] = level_id
data["assigned_to"] = username
path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
PY
}

wait_for_port() {
    local host="$1" port="$2" retries=60
    for i in $(seq 1 $retries); do
        if nc -z "$host" "$port" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

launch_bot_async() {
    (
        echo "🤖 等待服务器端口 ${BOT_HOST}:${BOT_PORT} 就绪后自动拉起 bot..."
        if wait_for_port "$BOT_HOST" "$BOT_PORT"; then
            create_default_bot_task
            echo "🤖 端口已就绪，启动 bot (task: $BOT_TASK_FILE)"
            EXTRA_BOT_ARGS=()
            if [ "$BOT_STAY_ONLINE" = "1" ]; then
                EXTRA_BOT_ARGS+=("--stay-online")
            fi
            NODE_ENV=staging node "$PROJECT_DIR/system/taskcrew/bridge.js" --mode apply --task-file "$BOT_TASK_FILE" --mc-host "$BOT_HOST" --mc-port "$BOT_PORT" --username "$BOT_USERNAME" --version "$BOT_VERSION" "${EXTRA_BOT_ARGS[@]}" || echo "⚠️ bot 启动失败"
        else
            echo "⚠️ bot 未启动：等待端口超时"
        fi
    ) &
}

# 端口占用检测/清理
MC_PORT=25565
RCON_PORT=${MINECRAFT_RCON_PORT:-25575}
RCON_PASSWORD=${MINECRAFT_RCON_PASSWORD:-drift_rcon_dev}
if command -v lsof >/dev/null 2>&1; then
    OCCUPIED_PIDS=$(lsof -ti tcp:$MC_PORT 2>/dev/null || true)
    if [ -n "$OCCUPIED_PIDS" ]; then
        echo "⚠️ 端口 $MC_PORT 已被占用，尝试结束相关进程: $OCCUPIED_PIDS"
        while read -r PID; do
            [ -z "$PID" ] && continue
            kill "$PID" 2>/dev/null || true
        done <<< "$OCCUPIED_PIDS"
        sleep 1
        STILL_OCCUPIED=$(lsof -ti tcp:$MC_PORT 2>/dev/null || true)
        if [ -n "$STILL_OCCUPIED" ]; then
            echo "⚠️ 进程未完全退出，执行强制结束: $STILL_OCCUPIED"
            while read -r PID; do
                [ -z "$PID" ] && continue
                kill -9 "$PID" 2>/dev/null || true
            done <<< "$STILL_OCCUPIED"
            sleep 1
        fi
    fi
fi

if command -v lsof >/dev/null 2>&1; then
    RCON_PIDS=$(lsof -ti tcp:$RCON_PORT 2>/dev/null || true)
    if [ -n "$RCON_PIDS" ]; then
        echo "⚠️ RCON 端口 $RCON_PORT 已被占用，尝试结束相关进程: $RCON_PIDS"
        while read -r PID; do
            [ -z "$PID" ] && continue
            kill "$PID" 2>/dev/null || true
        done <<< "$RCON_PIDS"
        sleep 1
        STILL_RCON=$(lsof -ti tcp:$RCON_PORT 2>/dev/null || true)
        if [ -n "$STILL_RCON" ]; then
            echo "⚠️ 进程未完全退出，执行强制结束: $STILL_RCON"
            while read -r PID; do
                [ -z "$PID" ] && continue
                kill -9 "$PID" 2>/dev/null || true
            done <<< "$STILL_RCON"
            sleep 1
        fi
    fi
fi

# 自动检测 jar 文件（Paper / Spigot / 其他）
JAR_FILE=$(ls | grep -E "paper|spigot|server.*\.jar" | head -n 1)

if [ -z "$JAR_FILE" ]; then
    echo "❌ 未找到 Minecraft 服务器 JAR 文件（paper/spigot）"
    exit 1
fi

echo "🔍 检测到服务器文件: $JAR_FILE"
echo "🧩 插件目录: plugins/"

# 检查插件是否存在
if [ ! -d "plugins" ]; then
    echo "⚠️ plugins 文件夹不存在，正在创建 ..."
    mkdir plugins
fi

echo "🚀 MC 服务器启动中..."
echo "（按 Ctrl+C 关闭）"

if [ -f "server.properties" ]; then
    echo "🛡 确保 RCON 配置启用..."
    export DRIFT_START_RCON_PORT="$RCON_PORT"
    export DRIFT_START_RCON_PASSWORD="$RCON_PASSWORD"
    python3 <<'PY'
from pathlib import Path
import os

path = Path("server.properties")
content = path.read_text(encoding="utf-8").splitlines()
updates = {
    "enable-rcon": "true",
    "broadcast-rcon-to-ops": "true",
    "rcon.port": os.environ.get("DRIFT_START_RCON_PORT", "25575"),
    "rcon.password": os.environ.get("DRIFT_START_RCON_PASSWORD", "drift_rcon_dev"),
}

keys = set(updates)
result = []
seen = set()
for line in content:
    stripped = line.strip()
    updated = False
    for key, value in updates.items():
        if stripped.startswith(f"{key}="):
            result.append(f"{key}={value}")
            seen.add(key)
            updated = True
            break
    if not updated:
        result.append(line)

missing = keys - seen
for key in missing:
    result.append(f"{key}={updates[key]}")

path.write_text("\n".join(result) + "\n", encoding="utf-8")
PY
    unset DRIFT_START_RCON_PORT
    unset DRIFT_START_RCON_PASSWORD
else
    echo "⚠️ 未找到 server.properties，无法自动写入 RCON 配置。"
fi

if [ -f "$AUTO_BUILD_PID" ]; then
    OLD_AUTO_PID=$(cat "$AUTO_BUILD_PID" 2>/dev/null)
    if [ -n "$OLD_AUTO_PID" ] && ps -p "$OLD_AUTO_PID" >/dev/null 2>&1; then
        echo "⚠️ 检测到之前的 auto_build watcher (PID: $OLD_AUTO_PID)，正在停止…"
        kill "$OLD_AUTO_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$AUTO_BUILD_PID"
fi

if [ -f "$AUTO_BUILD_SCRIPT" ]; then
    mkdir -p "$PROJECT_DIR/logs"
    WATCHER_ARGS=("--watch")
    WATCHER_HOST=${MINECRAFT_RCON_HOST:-localhost}
    WATCHER_PORT=${MINECRAFT_RCON_PORT:-25575}
    WATCHER_PASSWORD=${RCON_PASSWORD}
    if [ -n "$WATCHER_HOST" ]; then
        WATCHER_ARGS+=("--rcon-host" "$WATCHER_HOST")
    fi
    if [ -n "$WATCHER_PORT" ]; then
        WATCHER_ARGS+=("--rcon-port" "$WATCHER_PORT")
    fi
    if [ -n "$WATCHER_PASSWORD" ]; then
        WATCHER_ARGS+=("--rcon-password" "$WATCHER_PASSWORD")
    fi

    echo "🛠 重新启动 auto_build watcher…"
    (
        cd "$PROJECT_DIR" || exit 1
        nohup env PYTHONUNBUFFERED=1 python3 "$AUTO_BUILD_SCRIPT" "${WATCHER_ARGS[@]}" >> "$AUTO_BUILD_LOG" 2>&1 &
        AUTO_PID=$!
        echo "$AUTO_PID" > "$AUTO_BUILD_PID"
    )
else
    echo "⚠️ 未找到 $AUTO_BUILD_SCRIPT，跳过 auto_build watcher。"
fi

JAVA_FLAGS=(
    "-Xms2G"
    "-Xmx4G"
    "-Dterminal.jline=false"
    "-Dterminal.ansi=true"
)

if [ "$AUTO_BOT" = "1" ]; then
    launch_bot_async
fi

java "${JAVA_FLAGS[@]}" -jar "$JAR_FILE" nogui
