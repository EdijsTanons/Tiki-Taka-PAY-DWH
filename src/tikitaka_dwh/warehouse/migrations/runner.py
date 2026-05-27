"""Migration runner: applies SQL migration files in lexical order, idempotent."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent

_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS _schema_migrations (
    version     VARCHAR PRIMARY KEY,
    applied_at  TIMESTAMP NOT NULL DEFAULT current_timestamp
);
"""


def run_migrations(db_path: Path, migrations_dir: Path = _MIGRATIONS_DIR) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(_BOOTSTRAP)
        applied = {
            row[0] for row in con.execute("SELECT version FROM _schema_migrations").fetchall()
        }
        sql_files = sorted(p for p in migrations_dir.glob("*.sql"))
        for sql_file in sql_files:
            version = sql_file.stem
            if version in applied:
                logger.debug("Migration %s already applied, skipping.", version)
                continue
            logger.info("Applying migration %s …", version)
            sql = sql_file.read_text(encoding="utf-8")
            con.begin()
            try:
                con.execute(sql)
                con.execute(
                    "INSERT INTO _schema_migrations (version) VALUES (?)", [version]
                )
                con.commit()
                logger.info("Migration %s applied.", version)
            except Exception:
                con.rollback()
                logger.error("Migration %s failed — rolled back.", version, exc_info=True)
                raise
    finally:
        con.close()
