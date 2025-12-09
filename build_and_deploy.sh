#!/bin/bash
# 完整的 DriftSystem 构建和部署脚本

set -e  # 出错时退出

echo "========================================"
echo "  DriftSystem 一键构建部署"
echo "========================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 工作目录
WORKSPACE="/Users/zxydediannao/DriftSystem"
PLUGIN_DIR="$WORKSPACE/system/mc_plugin"
BACKEND_DIR="$WORKSPACE/backend"
SERVER_DIR="$WORKSPACE/backend/server"

cd "$WORKSPACE"

# ============================================================
# 1. 构建插件
# ============================================================
echo -e "${YELLOW}[1/5] 构建 Minecraft 插件...${NC}"
cd "$PLUGIN_DIR"

if [ -f "pom.xml" ]; then
    echo "  使用 Maven 构建..."
    mvn clean package -DskipTests -q
    
    if [ -f "target/DriftSystem-1.0.0.jar" ]; then
        echo -e "${GREEN}  ✓ 插件构建成功: DriftSystem-1.0.0.jar${NC}"
    else
        echo -e "${RED}  ✗ 插件构建失败${NC}"
        exit 1
    fi
else
    echo -e "${RED}  ✗ 找不到 pom.xml${NC}"
    exit 1
fi

# ============================================================
# 2. 部署插件到服务器
# ============================================================
echo ""
echo -e "${YELLOW}[2/5] 部署插件到 Minecraft 服务器...${NC}"

PLUGIN_JAR="$PLUGIN_DIR/target/mc_plugin-1.0-SNAPSHOT.jar"
PLUGIN_DEST="$SERVER_DIR/plugins/DriftSystem.jar"

if [ -f "$PLUGIN_JAR" ]; then
    mkdir -p "$SERVER_DIR/plugins"
    cp "$PLUGIN_JAR" "$PLUGIN_DEST"
    echo -e "${GREEN}  ✓ 插件已部署到: $PLUGIN_DEST${NC}"
else
    echo -e "${RED}  ✗ 找不到插件 JAR 文件${NC}"
    exit 1
fi

# ============================================================
# 3. 检查后端依赖
# ============================================================
echo ""
echo -e "${YELLOW}[3/5] 检查 Python 后端依赖...${NC}"
cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
    echo "  创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "  安装/更新依赖..."
pip install -r requirements.txt --quiet

if [ $? -eq 0 ]; then
    echo -e "${GREEN}  ✓ Python 依赖已就绪${NC}"
else
    echo -e "${RED}  ✗ Python 依赖安装失败${NC}"
    exit 1
fi

# ============================================================
# 4. 检查教学关卡文件
# ============================================================
echo ""
echo -e "${YELLOW}[4/5] 验证教学系统文件...${NC}"

TUTORIAL_LEVEL="$BACKEND_DIR/data/flagship_levels/tutorial_level.json"
if [ ! -f "$TUTORIAL_LEVEL" ]; then
    TUTORIAL_LEVEL="$BACKEND_DIR/data/heart_levels/tutorial_level.json"
fi

if [ -f "$TUTORIAL_LEVEL" ]; then
    echo -e "${GREEN}  ✓ 教学关卡文件存在${NC}"
    
    # 验证JSON格式
    python3 -c "import json; json.load(open('$TUTORIAL_LEVEL'))" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ 教学关卡JSON格式正确${NC}"
    else
        echo -e "${RED}  ✗ 教学关卡JSON格式错误${NC}"
        exit 1
    fi
else
    echo -e "${RED}  ✗ 教学关卡文件不存在${NC}"
    exit 1
fi

# ============================================================
# 5. 启动测试
# ============================================================
echo ""
echo -e "${YELLOW}[5/5] 准备启动服务...${NC}"
echo ""

# 检查端口占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}  ⚠ 端口 8000 已被占用${NC}"
    echo "  停止现有后端进程..."
    PID=$(lsof -ti:8000)
    kill -9 $PID 2>/dev/null || true
    sleep 2
fi

if lsof -Pi :25565 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}  ⚠ 端口 25565 已被占用${NC}"
    echo "  停止现有 MC 服务器..."
    PID=$(lsof -ti:25565)
    kill -9 $PID 2>/dev/null || true
    sleep 2
fi

# 删除世界锁文件
if [ -d "$SERVER_DIR/world" ]; then
    rm -f "$SERVER_DIR/world/session.lock"
    rm -f "$SERVER_DIR/world_nether/session.lock"
    rm -f "$SERVER_DIR/world_the_end/session.lock"
    echo -e "${GREEN}  ✓ 已清理世界锁文件${NC}"
fi

echo ""
echo -e "${GREEN}========================================"
echo "  构建部署完成！"
echo "========================================${NC}"
echo ""
echo "下一步："
echo "  1. 启动后端: cd $BACKEND_DIR && source venv/bin/activate && python app/main.py"
echo "  2. 启动 MC 服务器: cd $SERVER_DIR && java -jar server.jar"
echo ""
echo "或使用快速启动脚本："
echo "  ./start_all.sh"
echo ""

# 询问是否立即启动
read -p "是否现在启动所有服务？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}启动后端服务...${NC}"
    cd "$BACKEND_DIR"
    source venv/bin/activate
    python app/main.py > backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > backend.pid
    echo -e "${GREEN}  ✓ 后端已启动 (PID: $BACKEND_PID)${NC}"
    echo -e "  日志: $BACKEND_DIR/backend.log"
    
    sleep 3
    
    echo ""
    echo -e "${YELLOW}启动 Minecraft 服务器...${NC}"
    cd "$SERVER_DIR"
    
    # 查找服务器 JAR 文件
    SERVER_JAR=$(find . -maxdepth 1 -name "*.jar" -type f | head -n 1)
    
    if [ -z "$SERVER_JAR" ]; then
        echo -e "${RED}  ✗ 找不到服务器 JAR 文件${NC}"
        echo "  请手动启动: cd $SERVER_DIR && java -jar <server.jar>"
    else
        echo "  使用: $SERVER_JAR"
        nohup java -Xmx2G -Xms2G -jar "$SERVER_JAR" nogui > server.log 2>&1 &
        MC_PID=$!
        echo $MC_PID > server.pid
        echo -e "${GREEN}  ✓ MC 服务器已启动 (PID: $MC_PID)${NC}"
        echo -e "  日志: $SERVER_DIR/server.log"
        
        echo ""
        echo -e "${GREEN}所有服务已启动！${NC}"
        echo "  - 后端API: http://127.0.0.1:8000"
        echo "  - MC 服务器: localhost:25565"
        echo ""
        echo "查看日志:"
        echo "  tail -f $BACKEND_DIR/backend.log"
        echo "  tail -f $SERVER_DIR/logs/latest.log"
    fi
else
    echo "跳过启动，请手动启动服务。"
fi

echo ""
echo -e "${GREEN}完成！${NC}"
