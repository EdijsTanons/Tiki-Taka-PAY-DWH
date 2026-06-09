"""Tests for the warehouse migration runner."""

from __future__ import annotations

from pathlib import Path

import duckdb

from tikitaka_dwh.warehouse.migrations.runner import run_migrations


def _applied(db_path: Path) -> set[str]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return {r[0] for r in con.execute("SELECT version FROM _schema_migrations").fetchall()}
    finally:
        con.close()


def test_run_migrations_creates_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "wh.duckdb"
    run_migrations(db_path)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables"
            ).fetchall()
        }
    finally:
        con.close()

    assert "fct_documents" in tables
    assert "fct_sale_lines" in tables
    assert "fct_payments" in tables
    assert _applied(db_path)  # at least one migration recorded


def test_run_migrations_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "wh.duckdb"
    run_migrations(db_path)
    first = _applied(db_path)

    run_migrations(db_path)  # second run must be a no-op
    assert _applied(db_path) == first
