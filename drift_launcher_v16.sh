#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Drift Launcher v16 — 环境检测 + 自动修复 + 稳定版
# - 检测有环境就不重复安装
# - 自动修复 OpenAI / PIL 等依赖
# - 自动启动 Backend + MC 服务器
# - 100% ASCII，无 BOM，无 emoji，兼容 macOS Bash 3.2
###############################################################################

echo "===================================================="
echo "DriftSystem Launcher v16 - Environment Aware Version"
echo "===================================================="

###############################################################################
# 0. 全局环境检查（只提示 / 必要时才安装）
###############################################################################

echo "Checking environment ..."

# 检查 Homebrew（只用于可选安装）
if command -v brew >/dev/null 2>&1; then
    echo "Homebrew OK"
else
    echo "WARNING: Homebrew not found. Some auto-install features will be disabled."
fi

# 检查 Java
if command -v java >/dev/null 2>&1; then
    echo "Java OK: $(java -version 2>&1 | head -n 1)"
else
    echo "WARNING: Java not found. Please install Java 17 (Temurin or similar)."
fi

# 检查 Maven
if command -v mvn >/dev/null 2>&1; then
    echo "Maven OK: $(mvn -v | head -n 1)"
else
    echo "WARNING: Maven not found. Please install Maven (brew install maven)."
fi

# 选择 Python 解释器：优先 python3.11
PY_BIN=""
if command -v python3.11 >/dev/null 2>&1; then
    PY_BIN="$(command -v python3.11)"
else
    if command -v python3 >/dev/null 2>&1; then
        PY_BIN="$(command -v python3)"
    else
        echo "ERROR: No python3 found. Please install Python 3.11."
        exit 1
    fi
fi

PY_VERSION=$("$PY_BIN" -V 2>/dev/null | awk '{print $2}')
echo "Python selected: $PY_BIN ($PY_VERSION)"
echo ""

###############################################################################
# 1. 定位 DriftSystem 根目录（以脚本位置为锚点，不依赖当前工作目录）
###############################################################################

SCRIPT_PATH="$(cd "$(dirname "$0")" ; pwd)"
ROOT="$SCRIPT_PATH"

if [[ ! -d "$ROOT/backend" || ! -d "$ROOT/system" ]]; then
    PARENT="$(dirname "$SCRIPT_PATH")"
    if [[ -d "$PARENT/backend" && -d "$PARENT/system" ]]; then
        ROOT="$PARENT"
    else
        echo "ERROR: Could not locate DriftSystem root."
        echo "Checked: $SCRIPT_PATH and $PARENT"
        exit 1
    fi
fi

echo "Root directory: $ROOT"
echo ""

###############################################################################
# 2. 路径定义
###############################################################################

PLUGIN_SRC="$ROOT/system/mc_plugin"
BACKEND_DIR="$ROOT/backend"
MC_DIR="$ROOT/backend/server"
PLUGIN_TARGET="$MC_DIR/plugins"

BACKEND_PORT=8000
MC_PORT=25565

mkdir -p "$PLUGIN_TARGET"
mkdir -p "$MC_DIR"

###############################################################################
# 3. 检查 paper.jar（避免 cp 相同文件导致错误）
###############################################################################

echo "Checking PaperMC server jar ..."

FOUND=""
SEARCH_DIRS=("$MC_DIR" "$ROOT/server" "$ROOT" "$HOME/Downloads")
for dir in "${SEARCH_DIRS[@]}"; do
    [[ -d "$dir" ]] || continue
    CANDIDATE=$(find "$dir" -maxdepth 1 -type f -name "paper*.jar" | head -n 1)
    if [[ -n "$CANDIDATE" ]]; then
        FOUND="$CANDIDATE"
        break
    fi
done

if [[ -z "$FOUND" ]]; then
    echo "ERROR: PaperMC jar not found. Place paper-*.jar in backend/server/ or root."
    exit 1
fi

echo "Using PaperMC jar: $FOUND"

TARGET_JAR="$MC_DIR/paper.jar"
if [[ ! -f "$TARGET_JAR" ]] || ! cmp -s "$FOUND" "$TARGET_JAR" 2>/dev/null; then
    cp -f "$FOUND" "$TARGET_JAR"
    echo "PaperMC jar synced to $TARGET_JAR"
else
    echo "PaperMC jar already up to date."
fi
echo ""

###############################################################################
# 4. 清理占用端口
###############################################################################

echo "Clearing ports ..."

set +e
lsof -ti :$BACKEND_PORT | xargs kill -9 2>/dev/null
lsof -ti :$MC_PORT      | xargs kill -9 2>/dev/null
set -e

find "$MC_DIR" -maxdepth 2 -name session.lock -delete 2>/dev/null || true

echo "Ports cleared."
echo ""

###############################################################################
# 5. Python venv 检查 + 自动修复 Python 版本
###############################################################################

echo "Checking Python venv ..."

if [[ ! -d "$ROOT/venv" ]]; then
    echo "No venv found. Creating new venv with $PY_BIN ..."
    "$PY_BIN" -m venv "$ROOT/venv"
    echo "venv created."
else
    echo "Existing venv found."
    VENV_PY="$ROOT/venv/bin/python"
    if [[ -x "$VENV_PY" ]]; then
        VENV_VER=$("$VENV_PY" -V 2>/dev/null | awk '{print $2}')
        VENV_MAJOR=$(echo "$VENV_VER" | cut -d. -f1)
        VENV_MINOR=$(echo "$VENV_VER" | cut -d. -f2)
        echo "venv Python version: $VENV_VER"
        if (( VENV_MAJOR > 3 )) || (( VENV_MAJOR == 3 && VENV_MINOR > 12 )); then
            echo "venv Python too new for OpenAI. Recreating venv with $PY_BIN ..."
            rm -rf "$ROOT/venv"
            "$PY_BIN" -m venv "$ROOT/venv"
            echo "venv recreated."
        fi
    else
        echo "WARNING: venv python not executable. Recreating venv with $PY_BIN ..."
        rm -rf "$ROOT/venv"
        "$PY_BIN" -m venv "$ROOT/venv"
        echo "venv recreated."
    fi
fi

# 激活 venv
# shellcheck disable=SC1090
source "$ROOT/venv/bin/activate"
echo ""

###############################################################################
# 6. 安装 Backend 依赖（有就不重复装）
###############################################################################

echo "Installing backend dependencies (only if missing) ..."

pip install --upgrade pip wheel setuptools >/dev/null

# openai
python -c "import openai" >/dev/null 2>&1 || pip install 'openai==1.51.0'

# fastapi
python -c "import fastapi" >/dev/null 2>&1 || pip install 'fastapi==0.115.*'

# uvicorn
python -c "import uvicorn" >/dev/null 2>&1 || pip install 'uvicorn==0.31.*'

# httpx
python -c "import httpx" >/dev/null 2>&1 || pip install 'httpx==0.27.*'

# requirements.txt（如果有）
REQ="$BACKEND_DIR/requirements.txt"
if [[ -f "$REQ" ]]; then
    echo "Found requirements.txt, installing (may re-use existing packages) ..."
    pip install -r "$REQ" || true
fi

echo "Backend dependencies OK."
echo ""

###############################################################################
# 7. 修正 OpenAI client 调用（删除 proxies 参数）
###############################################################################

echo "Fixing OpenAI client calls (removing 'proxies=...') ..."

TARGET_FILES=$(grep -rl "OpenAI" "$BACKEND_DIR/app" || true)
for file in $TARGET_FILES; do
    sed -i '' 's/proxies=[^,)]*,//g' "$file" || true
done

echo "OpenAI client definitions cleaned."
echo ""

###############################################################################
# 8. 启动 Backend（带自动缺包修复）
###############################################################################

echo "Starting FastAPI backend with auto-repair ..."

cd "$BACKEND_DIR"

start_backend_bg() {
    uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" > /tmp/drift_backend.log 2>&1 &
    echo $! > /tmp/drift_backend.pid
}

kill_backend() {
    if [[ -f /tmp/drift_backend.pid ]]; then
        kill -9 "$(cat /tmp/drift_backend.pid)" 2>/dev/null || true
        rm -f /tmp/drift_backend.pid
    fi
}

# 缺包名映射表
fix_missing_pkg() {
    case "$1" in
        PIL|Image)   echo "Pillow" ;;
        yaml)        echo "PyYAML" ;;
        cv2)         echo "opencv-python" ;;
        *)           echo "$1" ;;
    esac
}

ATTEMPT=1
MAX_ATTEMPTS=5

while (( ATTEMPT <= MAX_ATTEMPTS )); do
    echo "Backend start attempt $ATTEMPT of $MAX_ATTEMPTS ..."

    kill_backend
    start_backend_bg
    sleep 2

    if ! grep -q "ModuleNotFoundError" /tmp/drift_backend.log 2>/dev/null; then
        echo "Backend started successfully."
        break
    fi

    RAW_MISSING=$(grep -o "ModuleNotFoundError: No module named '[^']*'" \
                  /tmp/drift_backend.log | sed -E "s/.*'([^']*)'.*/\1/" || true)

    if [[ -z "${RAW_MISSING:-}" ]]; then
        echo "ModuleNotFoundError detected but module name could not be parsed."
        ATTEMPT=$((ATTEMPT + 1))
        continue
    fi

    FIXED_MISSING=$(fix_missing_pkg "$RAW_MISSING")

    echo "Missing dependency detected: $RAW_MISSING"
    echo "Installing package: $FIXED_MISSING"
    pip install "$FIXED_MISSING" || true

    ATTEMPT=$((ATTEMPT + 1))
done

if (( ATTEMPT > MAX_ATTEMPTS )); then
    echo "ERROR: Backend auto-repair failed. Check /tmp/drift_backend.log"
    exit 1
fi

cd "$ROOT"
echo ""

###############################################################################
# 9. 构建 Minecraft 插件
###############################################################################

echo "Building Minecraft plugin ..."

if [[ ! -d "$PLUGIN_SRC" ]]; then
    echo "ERROR: Plugin source directory not found: $PLUGIN_SRC"
    exit 1
fi

cd "$PLUGIN_SRC"
mvn -q clean package
cd "$ROOT"

BUILT_JAR=$(ls "$PLUGIN_SRC"/target/*.jar 2>/dev/null | grep -v "original" | head -n 1 || true)

if [[ -z "${BUILT_JAR:-}" ]]; then
    echo "ERROR: No built plugin jar found in $PLUGIN_SRC/target"
    exit 1
fi

cp -f "$BUILT_JAR" "$PLUGIN_TARGET/"
echo "Plugin deployed to $PLUGIN_TARGET"
echo ""

###############################################################################
# 10. 启动 PaperMC
###############################################################################

echo "Launching PaperMC ..."

cd "$MC_DIR"
java -Xms1G -Xmx2G -jar paper.jar nogui &
MC_PID=$!
cd "$ROOT"

sleep 1
echo "PaperMC started with PID $MC_PID"
echo ""

echo "===================================================="
echo "DriftSystem launched successfully (v16)"
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Minecraft: localhost:$MC_PORT"
echo "Plugin dir: $PLUGIN_TARGET"
echo "===================================================="
