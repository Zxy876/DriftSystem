#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_PATH="${ROOT_DIR}/docs/payload_v2/evidence/gate2b_execution_replay_report.json"

PYTEST_CURRENT_TEST=gate2b_exec_dry_run python3 "${ROOT_DIR}/tools/gate2b_execution_replay_check.py" --rounds 100 --output "${OUTPUT_PATH}"

echo "Gate2B report generated: ${OUTPUT_PATH}"
