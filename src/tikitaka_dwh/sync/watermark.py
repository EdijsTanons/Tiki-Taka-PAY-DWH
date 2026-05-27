"""Watermark / sync-state tracking stored in DuckDB."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import duckdb

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS _sync_state (
    key            VARCHAR PRIMARY KEY,
    int_value      BIGINT,
    ts_value       TIMESTAMP,
    updated_at     TIMESTAMP NOT NULL DEFAULT current_timestamp
);
"""


class WatermarkStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._ensure_table()

    def _conn(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self._db_path))

    def _ensure_table(self) -> None:
        with self._conn() as con:
            con.execute(_DDL)

    def get_last_seen_id(self) -> Optional[int]:
        with self._conn() as con:
            row = con.execute(
                "SELECT int_value FROM _sync_state WHERE key = 'last_seen_id'"
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def set_last_seen_id(self, id_: int) -> None:
        with self._conn() as con:
            con.execute(
                """
                INSERT INTO _sync_state (key, int_value, updated_at)
                VALUES ('last_seen_id', ?, current_timestamp)
                ON CONFLICT (key) DO UPDATE SET int_value = excluded.int_value,
                                                updated_at = excluded.updated_at
                """,
                [id_],
            )

    def mark_sync_started(self) -> None:
        self._set_ts("last_sync_started_at")

    def mark_sync_completed(self) -> None:
        self._set_ts("last_sync_completed_at")

    def get_last_sync_completed(self) -> Optional[datetime]:
        with self._conn() as con:
            row = con.execute(
                "SELECT ts_value FROM _sync_state WHERE key = 'last_sync_completed_at'"
            ).fetchone()
        return row[0] if row else None

    def _set_ts(self, key: str) -> None:
        now = datetime.now(timezone.utc)
        with self._conn() as con:
            con.execute(
                """
                INSERT INTO _sync_state (key, ts_value, updated_at)
                VALUES (?, ?, current_timestamp)
                ON CONFLICT (key) DO UPDATE SET ts_value = excluded.ts_value,
                                                updated_at = excluded.updated_at
                """,
                [key, now],
            )
