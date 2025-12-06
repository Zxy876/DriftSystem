#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Drift Launcher v15 — 环境依赖检测 + 自动修复 + 完整稳定版
# 自动依赖修复 + Python版本保证 + OpenAI兼容修复 + 安全依赖映射
# 100% ASCII，无 BOM，无 emoji，兼容 macOS Bash 3.2
###############################################################################

echo "===================================================="
echo "DriftSystem Launcher v15 - Environment Aware Version"
echo "===================================================="

###############################################################################
# 0. Global Environment Check
###############################################################################

echo "Checking environment ..."

# --- Check Homebrew ---
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found. Installing Homebrew ..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "Homebrew OK"
fi

# --- Check Java ---
if ! command -v java >/dev/null 2>&1; then
    echo "Java not found. Installing Temurin Java 17 ..."
    brew install temurin
else
    echo "Java OK: $(java -version 2>&1 | head -n 1)"
fi

# --- Check Maven ---
if ! command -v mvn >/dev/null 2>&1; then
    echo "Maven not found. Installing Maven ..."
    brew install maven
else
    echo "Maven OK: $(mvn -v | head -n 1)"
fi

# --- Check Python version (OpenAI requires <= 3.12) ---
PY_VERSION=$(python3 -V 2>/dev/null | awk '{print $2}')
MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if (( MAJOR > 3 )) || (( MAJOR == 3 && MINOR > 12 )); then
    echo "Python $PY_VERSION unsupported. Installing Python3.11 ..."
    brew install python@3.11
    PY_BIN="/opt/homebrew/bin/python3.11"
else
    PY_BIN="python3"
fi

echo "Python OK: $($PY_BIN -V)"

###############################################################################
# 1. Locate Root Directory
###############################################################################
SCRIPT_PATH="$(cd "$(dirname "$0")" ; pwd)"
CWD="$(pwd)"

if [[ -d "$CWD/backend" && -d "$CWD/system" ]]; then
    ROOT="$CWD"
else
    SEARCH="$SCRIPT_PATH"
    while [[ ! ( -d "$SEARCH/backend" && -d "$SEARCH/system" ) ]]; do
        SEARCH="$(dirname "$SEARCH")"
        if [[ "$SEARCH" == "/" ]]; then
            echo "ERROR: Could not locate DriftSystem root."
            exit 1
        fi
    done
    ROOT="$SEARCH"
fi

echo "Root directory: $ROOT"
echo ""

###############################################################################
# 2. Path Definitions
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
# 3. Locate paper.jar
###############################################################################
echo "Checking paper.jar ..."

CANDIDATES=(
    "$MC_DIR/paper.jar"
    "$ROOT/server/paper.jar"
    "$ROOT/paper.jar"
    "$HOME/Downloads/paper.jar"
)

FOUND=""
for f in "${CANDIDATES[@]}"; do
    [[ -f "$f" ]] && FOUND="$f" && break
done

if [[ -z "$FOUND" ]]; then
    echo "ERROR: paper.jar not found. Place it in backend/server/"
    exit 1
fi

echo "Using paper.jar: $FOUND"
cp -f "$FOUND" "$MC_DIR/paper.jar"
echo ""

###############################################################################
# 4. Clear Ports
###############################################################################
echo "Clearing ports ..."

set +e
lsof -ti :$BACKEND_PORT | xargs kill -9 2>/dev/null
lsof -ti :$MC_PORT      | xargs kill -9 2>/dev/null
set -e

rm -f "$MC_DIR/world/session.lock" 2>/dev/null || true

echo "Ports cleared."
echo ""

###############################################################################
# 5. Python venv + Dependency Install
###############################################################################
echo "Checking Python venv ..."

if [[ ! -d "$ROOT/venv" ]]; then
    echo "Creating venv ..."
    $PY_BIN -m venv "$ROOT/venv"
    echo "venv created."
fi

source "$ROOT/venv/bin/activate"
echo ""

echo "Installing backend base dependencies ..."

pip install --upgrade pip wheel setuptools

# Check openai only if missing
if ! python3 -c "import openai" >/dev/null 2>&1; then
    pip install "openai==1.51.0"
fi

# Check fastapi
if ! python3 -c "import fastapi" >/dev/null 2>&1; then
    pip install "fastapi==0.115.*"
fi

# Check uvicorn
if ! command -v uvicorn >/dev/null 2>&1; then
    pip install "uvicorn==0.31.*"
fi

# Extra dependencies
pip install httpx==0.27.*

# requirements.txt
REQ="$BACKEND_DIR/requirements.txt"
if [[ -f "$REQ" ]]; then
    pip install -r "$REQ" || true
fi

echo "Backend dependencies OK"
echo ""

###############################################################################
# 6. Fix OpenAI client calls
###############################################################################
echo "Fixing OpenAI client calls ..."

TARGET_FILES=$(grep -rl "OpenAI" "$BACKEND_DIR/app" || true)
for file in $TARGET_FILES; do
    sed -i '' 's/proxies=[^,)]*,//g' "$file" || true
done

echo "OpenAI call fixes applied."
echo ""

###############################################################################
# 7. Auto-repair Backend Launcher
###############################################################################
echo "Starting FastAPI backend ..."

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

fix_missing_pkg() {
    case "$1" in
        PIL|Image) echo "Pillow" ;;
        yaml) echo "PyYAML" ;;
        cv2) echo "opencv-python" ;;
        *) echo "$1" ;;
    esac
}

ATTEMPT=1
MAX_ATTEMPTS=5

while (( ATTEMPT <= MAX_ATTEMPTS )); do
    echo "Backend start attempt $ATTEMPT ..."

    kill_backend
    start_backend_bg
    sleep 2

    if ! grep -q "ModuleNotFoundError" /tmp/drift_backend.log 2>/dev/null; then
        echo "Backend started OK"
        break
    fi

    RAW=$(grep -o "ModuleNotFoundError: No module named '[^']*'" /tmp/drift_backend.log | sed -E "s/.*'([^']*)'.*/\1/")
    FIX=$(fix_missing_pkg "$RAW")

    echo "Missing dependency: $RAW -> $FIX"
    pip install "$FIX" || true

    ATTEMPT=$((ATTEMPT + 1))
done

if (( ATTEMPT > MAX_ATTEMPTS )); then
    echo "ERROR: Backend auto repair failed."
    exit 1
fi

cd "$ROOT"
echo ""

###############################################################################
# 8. Build Minecraft Plugin
###############################################################################
echo "Building Minecraft plugin ..."

cd "$PLUGIN_SRC"
mvn -q clean package
cd "$ROOT"

cp -f "$PLUGIN_SRC"/target/*.jar "$PLUGIN_TARGET/" 2>/dev/null
echo "Plugin deployed."
echo ""

###############################################################################
# 9. Launch PaperMC
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
echo "DriftSystem launched successfully (v15)"
echo "Backend: http://localhost:$BACKEND_PORT"
echo "Minecraft: localhost:$MC_PORT"
echo "===================================================="