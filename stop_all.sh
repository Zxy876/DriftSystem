#!/bin/bash
# 停止所有 DriftSystem 服务

WORKSPACE="/Users/zxydediannao/DriftSystem"
BACKEND_DIR="$WORKSPACE/backend"
SERVER_DIR="$WORKSPACE/backend/server"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "  DriftSystem 停止服务"
echo "========================================"

# 停止后端
if [ -f "$BACKEND_DIR/backend.pid" ]; then
    PID=$(cat "$BACKEND_DIR/backend.pid")
    echo -e "${YELLOW}停止后端 (PID: $PID)...${NC}"
    kill -9 $PID 2>/dev/null || true
    rm -f "$BACKEND_DIR/backend.pid"
    echo -e "${GREEN}  ✓ 后端已停止${NC}"
else
    # 尝试通过端口停止
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        PID=$(lsof -ti:8000)
        kill -9 $PID 2>/dev/null || true
        echo -e "${GREEN}  ✓ 后端已停止 (端口 8000)${NC}"
    else
        echo "  后端未运行"
    fi
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
    if lsof -Pi :25565 -sTCP:LISTEN -t >/dev/null 2>&1; then
        PID=$(lsof -ti:25565)
        kill -9 $PID 2>/dev/null || true
        echo -e "${GREEN}  ✓ MC 服务器已停止 (端口 25565)${NC}"
    else
        echo "  MC 服务器未运行"
    fi
fi

# 清理锁文件
rm -f "$SERVER_DIR/world/session.lock" 2>/dev/null
rm -f "$SERVER_DIR/world_nether/session.lock" 2>/dev/null
rm -f "$SERVER_DIR/world_the_end/session.lock" 2>/dev/null

echo ""
echo -e "${GREEN}所有服务已停止${NC}"
