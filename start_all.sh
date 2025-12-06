#!/bin/bash

# =========================================
# DriftSystem 一键启动脚本
# =========================================

set -e

echo "========================================="
echo "  DriftSystem / 心悦宇宙"
echo "  完全自然语言驱动的AI冒险系统"
echo "========================================="

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# =========================================
# 步骤1: 检查环境
# =========================================
echo ""
echo -e "${BLUE}步骤1/4: 检查环境...${NC}"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python3 已安装${NC}"

# 检查Java
if ! command -v java &> /dev/null; then
    echo -e "${RED}❌ Java 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Java 已安装${NC}"

# 检查Maven
if ! command -v mvn &> /dev/null; then
    echo -e "${RED}❌ Maven 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Maven 已安装${NC}"

# =========================================
# 步骤2: 启动后端
# =========================================
echo ""
echo -e "${BLUE}步骤2/4: 启动后端服务...${NC}"

cd "$SCRIPT_DIR/backend"

# 创建虚拟环境(如果不存在)
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建Python虚拟环境...${NC}"
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo -e "${YELLOW}安装Python依赖...${NC}"
pip install -q -r requirements.txt

# 启动后端(后台运行)
echo -e "${GREEN}启动后端服务...${NC}"
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > backend.pid

echo -e "${GREEN}✓ 后端服务已启动 (PID: $BACKEND_PID)${NC}"
echo -e "${GREEN}✓ 日志文件: backend.log${NC}"

# 等待后端启动
echo -e "${YELLOW}等待后端就绪...${NC}"
sleep 3

# 验证后端
if curl -s http://127.0.0.1:8000/ > /dev/null; then
    echo -e "${GREEN}✓ 后端运行正常${NC}"
else
    echo -e "${RED}❌ 后端启动失败，请查看 backend.log${NC}"
    exit 1
fi

# =========================================
# 步骤3: 构建MC插件
# =========================================
echo ""
echo -e "${BLUE}步骤3/4: 构建MC插件...${NC}"

cd "$SCRIPT_DIR/system/mc_plugin"

echo -e "${YELLOW}编译插件...${NC}"
mvn clean package -q

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 插件编译成功${NC}"
    
    # 复制到服务器
    JAR_FILE=$(find target -name "*.jar" ! -name "*-original.jar" | head -1)
    if [ -n "$JAR_FILE" ]; then
        cp "$JAR_FILE" "$SCRIPT_DIR/backend/server/plugins/DriftSystem.jar"
        echo -e "${GREEN}✓ 插件已复制到服务器${NC}"
    fi
else
    echo -e "${RED}❌ 插件编译失败${NC}"
    exit 1
fi

# =========================================
# 步骤4: 提示启动MC服务器
# =========================================
echo ""
echo -e "${BLUE}步骤4/4: 启动Minecraft服务器${NC}"
echo ""
echo -e "${YELLOW}=========================================${NC}"
echo -e "${GREEN}  后端服务已启动！${NC}"
echo -e "${GREEN}  插件已准备就绪！${NC}"
echo -e "${YELLOW}=========================================${NC}"
echo ""
echo -e "${YELLOW}下一步:${NC}"
echo "  1. 进入服务器目录:"
echo "     cd $SCRIPT_DIR/backend/server"
echo ""
echo "  2. 启动Minecraft服务器:"
echo "     java -Xmx4G -Xms2G -jar paper-*.jar"
echo ""
echo "  3. 进入游戏后测试:"
echo "     /drift status"
echo "     在聊天中说: 你好"
echo ""
echo -e "${YELLOW}停止后端服务:${NC}"
echo "  kill $BACKEND_PID"
echo "  或运行: kill \$(cat $SCRIPT_DIR/backend/backend.pid)"
echo ""
echo -e "${YELLOW}查看后端日志:${NC}"
echo "  tail -f $SCRIPT_DIR/backend/backend.log"
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  DriftSystem 准备完成！${NC}"
echo -e "${GREEN}  享受你的AI冒险之旅！ 🚀${NC}"
echo -e "${GREEN}=========================================${NC}"
