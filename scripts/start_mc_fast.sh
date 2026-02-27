#!/usr/bin/env bash
set -euo pipefail

# Fast start for daily use:
# - no git pull
# - no plugin rebuild
# - no backend local restart
# - start/restart MC + health checks only

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DO_GIT_PULL=0 \
BUILD_PLUGIN=0 \
RESTART_BACKEND_LOCAL=0 \
RESTART_MC=1 \
RUN_STORY_SMOKE=0 \
./scripts/oneclick_server_ops.sh "$@"
