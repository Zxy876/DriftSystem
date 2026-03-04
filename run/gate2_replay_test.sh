#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_PATH="${ROOT_DIR}/docs/payload_v2/evidence/gate2_replay_report.json"

python3 "${ROOT_DIR}/tools/gate2_replay_determinism_check.py" --rounds 100 --output "${OUTPUT_PATH}"

echo "Gate2 report generated: ${OUTPUT_PATH}"
