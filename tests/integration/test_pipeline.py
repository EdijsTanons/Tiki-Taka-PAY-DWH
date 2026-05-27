"""Integration test: raw write → transform → warehouse load → query."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from tikitaka_dwh.sync.raw_writer import RawWriter
from tikitaka_dwh.transform.documents import build_documents
from tikitaka_dwh.transform.sale_lines import build_sale_lines
from tikitaka_dwh.transform.payments import build_payments
from tikitaka_dwh.warehouse.db import initialize_warehouse, get_connection, _upsert_df


def test_full_pipeline(tmp_path: Path, sample_docs: list):
    run_id = uuid.uuid4().hex
    raw_dir = tmp_path / "lake" / "raw"

    # Step 1: write raw
    writer = RawWriter(raw_dir, run_id)
    writer.write_page(sample_docs)
    assert len(list(raw_dir.rglob("*.json"))) == 1

    # Step 2: transform
    df_docs = build_documents(sample_docs)
    df_lines = build_sale_lines(sample_docs)
    df_pmts = build_payments(sample_docs)

    assert len(df_docs) == 5
    assert len(df_lines) == 13  # 8 + 3 + 2 sale lines
    assert len(df_pmts) >= 3

    # Step 3: load into warehouse
    db_path = tmp_path / "warehouse.duckdb"
    initialize_warehouse(db_path)

    con = get_connection(db_path)
    try:
        _upsert_df(con, df_docs, "fct_documents", ["id"])
        _upsert_df(con, df_lines, "fct_sale_lines", ["doc_id", "row_num"])
        _upsert_df(con, df_pmts, "fct_payments", ["doc_id", "payment_seq"])
        con.commit()

        count = con.execute("SELECT COUNT(*) FROM fct_documents").fetchone()[0]
        assert count == 5

        sale_count = con.execute(
            "SELECT COUNT(*) FROM fct_documents WHERE doc_type = 'sale'"
        ).fetchone()[0]
        assert sale_count == 3

        line_count = con.execute("SELECT COUNT(*) FROM fct_sale_lines").fetchone()[0]
        assert line_count == 13

        # FK closure: every sale line references a document
        orphans = con.execute(
            "SELECT COUNT(*) FROM fct_sale_lines sl "
            "LEFT JOIN fct_documents fd ON sl.doc_id = fd.id "
            "WHERE fd.id IS NULL"
        ).fetchone()[0]
        assert orphans == 0
    finally:
        con.close()


def test_watermark(tmp_path: Path):
    from tikitaka_dwh.sync.watermark import WatermarkStore

    db_path = tmp_path / "wm.duckdb"
    wm = WatermarkStore(db_path)
    assert wm.get_last_seen_id() is None
    wm.set_last_seen_id(42)
    assert wm.get_last_seen_id() == 42
    wm.set_last_seen_id(100)
    assert wm.get_last_seen_id() == 100
