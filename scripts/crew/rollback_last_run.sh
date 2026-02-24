#!/usr/bin/env bash
# Rollback last crew run snapshot (Issue 3.4)
# 允许 dry-run，打印将恢复的文件列表；缺少快照时提示人工补录。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORLD_DIR="${WORLD_DIR_OVERRIDE:-$REPO_ROOT/server/world}"
LOG_ROOT="${DRIFT_CREW_RUNS_DIR:-$REPO_ROOT/backend/logs/crew_runs}"
DRY_RUN=1

print_usage() {
  echo "Usage: $0 [--apply]"
  echo "Default is dry-run (no files changed)."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      DRY_RUN=0
      shift
      ;;
    --help|-h)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      print_usage
      exit 1
      ;;
  esac

done

find_latest_run() {
  if [ ! -d "$LOG_ROOT" ]; then
    return 1
  fi
  ls -1d "$LOG_ROOT"/*/ 2>/dev/null | sort -r | head -n 1
}

RUN_DIR="$(find_latest_run || true)"
if [ -z "$RUN_DIR" ]; then
  echo "未找到 crew_runs 目录，无法回滚。请先确认已有 run 目录。"
  exit 1
fi

SNAPSHOT_DIR="$RUN_DIR/world_snapshot"
ROLLBACK_LOG="$RUN_DIR/rollback.log"
RUN_ID="$(basename "$RUN_DIR")"

ts() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log_line() {
  printf '[%s] %s\n' "$(ts)" "$1" | tee -a "$ROLLBACK_LOG"
}

log_line "mode=$([ "$DRY_RUN" -eq 1 ] && echo dry-run || echo apply) run=$RUN_ID src=$SNAPSHOT_DIR dst=$WORLD_DIR"

if [ ! -d "$SNAPSHOT_DIR" ]; then
  log_line "缺少快照目录：$SNAPSHOT_DIR，请人工补录后重试"
  exit 1
fi

mkdir -p "$WORLD_DIR"

RSYNC_FLAGS=("-avu" "--delete" "--itemize-changes")
if [ "$DRY_RUN" -eq 1 ]; then
  RSYNC_FLAGS=("-avun" "--delete" "--itemize-changes")
fi

log_line "开始同步（rsync ${RSYNC_FLAGS[*]}）"
rsync "${RSYNC_FLAGS[@]}" "$SNAPSHOT_DIR/" "$WORLD_DIR/" | tee -a "$ROLLBACK_LOG"

if [ "$DRY_RUN" -eq 1 ]; then
  log_line "dry-run 完成，未修改 world/。"
else
  log_line "apply 完成，world/ 已回滚至 $RUN_ID 的快照。"
fi
