"""Actor memory store using sqlite (Issue 4.1).

模块角色：存取演员记忆（长期与场景），支持按阶段读写。
不做什么：不调用模型、不做推理，仅做数据持久化；不修改世界状态。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional

STAGES = {"IMPORT", "SET_DRESS", "REHEARSE", "TAKE"}


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS long_term (
            actor_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (actor_id, key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scene (
            session_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (session_id, actor_id, key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session (
            session_id TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _serialize(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _deserialize(text: str):
    return json.loads(text)


class ActorMemoryStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            _ensure_tables(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        return conn

    def save_memory(
        self,
        actor_id: str,
        stage: str,
        data: Dict[str, object],
        session_id: Optional[str] = None,
        updated_at: str | None = None,
    ) -> None:
        if stage not in STAGES:
            msg = f"invalid stage: {stage}"
            raise ValueError(msg)
        if stage == "REHEARSE" and session_id is None:
            msg = "REHEARSE stage requires session_id"
            raise ValueError(msg)

        ts = updated_at or datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            if stage != "REHEARSE":
                for key, value in data.items():
                    cursor.execute(
                        """
                        INSERT INTO long_term(actor_id, key, value) VALUES(?,?,?)
                        ON CONFLICT(actor_id, key) DO UPDATE SET value=excluded.value
                        """,
                        (actor_id, key, _serialize(value)),
                    )
            if session_id is not None:
                for key, value in data.items():
                    cursor.execute(
                        """
                        INSERT INTO scene(session_id, actor_id, key, value) VALUES(?,?,?,?)
                        ON CONFLICT(session_id, actor_id, key) DO UPDATE SET value=excluded.value
                        """,
                        (session_id, actor_id, key, _serialize(value)),
                    )
                cursor.execute(
                    """
                    INSERT INTO session(session_id, stage, updated_at) VALUES(?,?,?)
                    ON CONFLICT(session_id) DO UPDATE SET stage=excluded.stage, updated_at=excluded.updated_at
                    """,
                    (session_id, stage, ts),
                )
            conn.commit()

    def load_memory(
        self, actor_id: str, stage: str, session_id: Optional[str] = None
    ) -> Dict[str, object]:
        if stage not in STAGES:
            msg = f"invalid stage: {stage}"
            raise ValueError(msg)
        result: Dict[str, object] = {}
        with self._connect() as conn:
            cursor = conn.cursor()
            for row in cursor.execute(
                "SELECT key, value FROM long_term WHERE actor_id=?", (actor_id,)
            ):
                result[row[0]] = _deserialize(row[1])
            if session_id is not None:
                for row in cursor.execute(
                    "SELECT key, value FROM scene WHERE session_id=? AND actor_id=?",
                    (session_id, actor_id),
                ):
                    result[row[0]] = _deserialize(row[1])
        return result

    def list_sessions(self) -> Iterable[str]:
        with self._connect() as conn:
            cursor = conn.cursor()
            sessions = [row[0] for row in cursor.execute("SELECT session_id FROM session")]
        return sessions


__all__ = ["ActorMemoryStore", "STAGES"]
