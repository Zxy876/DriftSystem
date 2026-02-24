#!/bin/bash
# 停止所有 DriftSystem 服务并确保进程与锁文件干净

set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$WORKSPACE/backend"
SERVER_DIR="$WORKSPACE/backend/server"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "  DriftSystem 停止服务"
echo "========================================"

kill_by_port() {
    local port="$1"
    if lsof -Pi ":$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
        local pids
        pids=$(lsof -ti":$port")
        echo -e "${YELLOW}停止端口 $port (PID: $pids)...${NC}"
        kill -9 $pids 2>/dev/null || true
        echo -e "${GREEN}  ✓ 端口 $port 相关进程已停止${NC}"
    else
        return 1
    fi
}

kill_by_pattern() {
    local pattern="$1"
    if pgrep -f "$pattern" >/dev/null 2>&1; then
        local pids
        pids=$(pgrep -f "$pattern")
        echo -e "${YELLOW}停止进程匹配: $pattern (PID: $pids)...${NC}"
        kill -9 $pids 2>/dev/null || true
        echo -e "${GREEN}  ✓ 进程 $pattern 已停止${NC}"
    else
        return 1
    fi
}

# 停止后端
if [ -f "$BACKEND_DIR/backend.pid" ]; then
    PID=$(cat "$BACKEND_DIR/backend.pid")
    echo -e "${YELLOW}停止后端 (PID: $PID)...${NC}"
    kill -9 $PID 2>/dev/null || true
    rm -f "$BACKEND_DIR/backend.pid"
    echo -e "${GREEN}  ✓ 后端已停止${NC}"
else
    # 尝试通过端口停止
    kill_by_port 8000 || echo "  后端未运行"
fi

# 停止 MC 服务器
if [ -f "$SERVER_DIR/server.pid" ]; then
    PID=$(cat "$SERVER_DIR/server.pid")
    echo -e "${YELLOW}停止 MC 服务器 (PID: $PID)...${NC}"
    kill -9 $PID 2>/dev/null || true
    rm -f "$SERVER_DIR/server.pid"
    echo -e "${GREEN}  ✓ MC 服务器已停止${NC}"
else
    # 尝试通过端口停止
    kill_by_port 25565 || echo "  MC 服务器未运行"
fi

# 额外清理：RCON、残留 Paper/Node 进程
kill_by_port 25575 || echo "  RCON 未运行"
kill_by_pattern "paper-1.20.1.jar" || true
kill_by_pattern "system/taskcrew/bridge.js" || true
kill_by_pattern "start_mc.sh" || true

# 清理锁文件
rm -f "$SERVER_DIR/world/session.lock" 2>/dev/null
rm -f "$SERVER_DIR/world_nether/session.lock" 2>/dev/null
rm -f "$SERVER_DIR/world_the_end/session.lock" 2>/dev/null
rm -f "$SERVER_DIR/world_staging_v121/session.lock" 2>/dev/null
rm -f "$SERVER_DIR/world_staging_v121_nether/session.lock" 2>/dev/null
rm -f "$SERVER_DIR/world_staging_v121_the_end/session.lock" 2>/dev/null

# 删除残留 pid 记录
rm -f "$BACKEND_DIR/backend.pid" 2>/dev/null
rm -f "$SERVER_DIR/server.pid" 2>/dev/null

# 清理临时日志
rm -f /tmp/start_mc.out 2>/dev/null

echo ""
echo -e "${GREEN}所有服务已停止${NC}"
