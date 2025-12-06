#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Drift Launcher v10.1 — 自动修复依赖 + 防止隐藏字符错误 + 超稳版本
###############################################################################

echo "===================================================="
echo "✨ DriftSystem 启动器 v10.1 — 自愈后端 + BOM 安全修复"
echo "===================================================="

# -----------------------------------------------------------------------------
# 1. 自动定位 DriftSystem 根目录
# -----------------------------------------------------------------------------
SCRIPT_PATH="$(cd "$(dirname "$0")"; pwd)"
CWD="$(pwd)"

if [[ -d "$CWD/backend" && -d "$CWD/system" ]]; then
    ROOT="$CWD"
else
    SEARCH="$SCRIPT_PATH"
    while [[ ! ( -d "$SEARCH/backend" && -d "$SEARCH/system" ) ]]; do
        SEARCH="$(dirname "$SEARCH")"
        if [[ "$SEARCH" == "/" ]]; then
            echo "❌ 无法找到 DriftSystem 根目录"
            exit 1
        fi
    done
    ROOT="$SEARCH"
fi

echo "✔ 项目根目录: $ROOT"
echo ""

PLUGIN_SRC="$ROOT/system/mc_plugin"
BACKEND_DIR="$ROOT/backend"
MC_DIR="$ROOT/backend/server"
PLUGIN_TARGET="$MC_DIR/plugins"

BACKEND_PORT=8000
MC_PORT=25565

mkdir -p "$PLUGIN_TARGET"
mkdir -p "$MC_DIR"

# -----------------------------------------------------------------------------
# 2. 查找 paper.jar
# -----------------------------------------------------------------------------
echo "🔍 查找 paper.jar ..."

CANDIDATES=(
    "$MC_DIR/paper.jar"
    "$ROOT/server/paper.jar"
    "$ROOT/paper.jar"
    "$HOME/Downloads/paper.jar"
)

FOUND=""

for f in "${CANDIDATES[@]}"; do
    if [[ -f "$f" ]]; then
        FOUND="$f"
        break
    fi
done

if [[ -z "$FOUND" ]]; then
    echo "❌ 未找到 paper.jar，请放入 backend/server/"
    exit 1
fi

echo "✔ 使用 paper.jar: $FOUND"

if ! cmp -s "$FOUND" "$MC_DIR/paper.jar" 2>/dev/null; then
    cp -f "$FOUND" "$MC_DIR/paper.jar"
    echo "✔ paper.jar 已更新"
else
    echo "✔ paper.jar 已是最新"
fi
echo ""

# -----------------------------------------------------------------------------
# 3. 清理端口
# -----------------------------------------------------------------------------
echo "🧹 清理端口占用..."

set +e
kill -9 $(lsof -ti :$BACKEND_PORT) 2>/dev/null
kill -9 $(lsof -ti :$MC_PORT) 2>/dev/null
set -e

rm -f "$MC_DIR/world/session.lock" 2>/dev/null || true

echo "✔ 端口清理完成"
echo ""

# -----------------------------------------------------------------------------
# 4. venv 检查
# -----------------------------------------------------------------------------
echo "🐍 检查 Python 虚拟环境..."

if [[ ! -d "$ROOT/venv" ]]; then
    echo "⚠️ 未找到 venv，正在创建..."
    python3 -m venv "$ROOT/venv"
    echo "✔ venv 创建完成"
fi

source "$ROOT/venv/bin/activate"
echo ""

# -----------------------------------------------------------------------------
# 5. 自动安装 requirements
# -----------------------------------------------------------------------------
REQ="$BACKEND_DIR/requirements.txt"

echo "📦 检查 backend 依赖..."

if [[ -f "$REQ" ]]; then
    pip install -q -r "$REQ" || true
    echo "✔ requirements 已安装"
else
    echo "⚠️ 未找到 requirements.txt (跳过)"
fi
echo ""

# -----------------------------------------------------------------------------
# 6. 自动修复启动后端
# -----------------------------------------------------------------------------
echo "⚡ 启动 FastAPI 后端（带自动修复）..."

cd "$BACKEND_DIR"

start_backend() {
    uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT" 2>&1
}

ATTEMPT=1
MAX_ATTEMPTS=5

while (( ATTEMPT <= MAX_ATTEMPTS )); do

    echo " 启动后端（尝试 $ATTEMPT/$MAX_ATTEMPTS）..."
    LOG=$(start_backend | tee /tmp/drift_backend_error.log || true)

    if ! grep -q "ModuleNotFoundError" <<< "$LOG"; then
        echo "✔ 后端已成功启动"
        break
    fi

    MISSING=$(grep -o "ModuleNotFoundError: No module named '[^']*'" /tmp/drift_backend_error.log | \
        sed -E "s/.*'([^']*)'.*/\1/")

    if [[ -n "$MISSING" ]]; then
        echo "⚠️ 缺少依赖: $MISSING"
        echo "📦 自动安装 $MISSING ..."
        pip install "$MISSING" || true
    fi

    ATTEMPT=$((ATTEMPT+1))
done

if (( ATTEMPT > MAX_ATTEMPTS )); then
    echo "❌ 自动修复失败，请检查 /tmp/drift_backend_error.log"
    exit 1
fi

cd "$ROOT"
echo ""

# -----------------------------------------------------------------------------
# 7. 构建 Minecraft 插件
# -----------------------------------------------------------------------------
echo "🔧 构建 Minecraft 插件..."

cd "$PLUGIN_SRC"
mvn -q clean package
cd "$ROOT"

BUILT_JAR=$(ls "$PLUGIN_SRC"/target/*.jar | grep -v "original" | head -n 1)

cp -f "$BUILT_JAR" "$PLUGIN_TARGET/"
echo "✔ 插件已部署到 $PLUGIN_TARGET"
echo ""

# -----------------------------------------------------------------------------
# 8. 启动 PaperMC
# -----------------------------------------------------------------------------
echo "🎮 启动 PaperMC..."

cd "$MC_DIR"
java -Xms1G -Xmx2G -jar paper.jar nogui &
MC_PID=$!
cd "$ROOT"

sleep 1
echo "✔ PaperMC 已启动 PID=$MC_PID"
echo ""

echo "===================================================="
echo "🎉 DriftSystem 启动成功 (v10.1)"
echo "📌 后端：http://localhost:$BACKEND_PORT"
echo "📌 Minecraft：localhost:$MC_PORT"
echo "📌 插件目录：$PLUGIN_TARGET"
echo "📌 PaperMC：$MC_DIR"
echo "===================================================="