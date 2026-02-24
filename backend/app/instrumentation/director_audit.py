"""Director decision audit logger (Issue 5.2).

模块角色：记录导演审批/指令的决策日志（JSONL）。
不做什么：不做权限判断，不调用模型，仅负责追加日志。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DIRECTOR_AUDIT_LOG = Path(
    os.environ.get("DRIFT_DIRECTOR_AUDIT_LOG", "backend/logs/director_decisions.jsonl")
)


def log_decision(
    *,
    player_id: str,
    decision: str,
    reason: str,
    level_id: str,
    session_state: Optional[str] = None,
) -> None:
    DIRECTOR_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "player_id": player_id,
        "decision": decision,
        "reason": reason,
        "level_id": level_id,
        "session_state": session_state,
    }
    with DIRECTOR_AUDIT_LOG.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


__all__ = ["log_decision", "DIRECTOR_AUDIT_LOG"]
