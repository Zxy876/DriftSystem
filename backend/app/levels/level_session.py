"""LevelSession 状态机（v1.21 四阶段）。

模块角色：管理 Level-as-Script 的阶段流转，持久化到 sqlite。
不做什么：不写世界、不执行业务侧布景/彩排/拍摄，只记录状态与合法迁移。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


STAGES = ("IMPORTED", "SET_DRESS", "REHEARSE", "TAKE")
ALLOWED_TRANSITIONS = {
    "IMPORTED": "SET_DRESS",
    "SET_DRESS": "REHEARSE",
    "REHEARSE": "TAKE",
}


class LevelSessionStore:
    """LevelSession 的持久化存储与状态机控制。"""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS level_sessions (
                    level_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_actor TEXT
                );
                """
            )
            conn.commit()

    def create_session(self, level_id: str) -> None:
        """创建新会话，初始状态为 IMPORTED；已存在则保持原状态。"""

        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT state FROM level_sessions WHERE level_id = ?",
                (level_id,),
            )
            if cur.fetchone():
                return
            conn.execute(
                "INSERT INTO level_sessions(level_id, state, updated_at) VALUES (?, ?, ?)",
                (level_id, "IMPORTED", now),
            )
            conn.commit()

    def get_state(self, level_id: str) -> Optional[str]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT state FROM level_sessions WHERE level_id = ?",
                (level_id,),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def advance(self, level_id: str, target_state: str, actor_id: str | None = None) -> str:
        """推进状态，遵守固定顺序；返回新状态。"""

        if target_state not in STAGES:
            raise ValueError(f"非法状态: {target_state}")

        with self._connect() as conn:
            cur = conn.execute(
                "SELECT state FROM level_sessions WHERE level_id = ?",
                (level_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"不存在的 level_id: {level_id}")

            current = row[0]
            expected = ALLOWED_TRANSITIONS.get(current)
            if expected != target_state:
                raise ValueError(f"非法跳转: {current} → {target_state}")

            now = datetime.utcnow().isoformat()
            conn.execute(
                "UPDATE level_sessions SET state = ?, updated_at = ?, last_actor = ? WHERE level_id = ?",
                (target_state, now, actor_id, level_id),
            )
            conn.commit()

        return target_state


__all__ = ["LevelSessionStore", "STAGES", "ALLOWED_TRANSITIONS"]