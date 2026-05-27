"""DuckDB connection management and staging loader."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from tikitaka_dwh.warehouse.migrations.runner import run_migrations

logger = logging.getLogger(__name__)


def get_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path))


def initialize_warehouse(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    run_migrations(db_path)
    logger.info("Warehouse initialized at %s", db_path)


# ---------------------------------------------------------------------------
# Loaders: upsert DataFrames into warehouse tables
# ---------------------------------------------------------------------------


def _upsert_df(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    table: str,
    pk_cols: list[str],
) -> None:
    if df.empty:
        return
    df = df.drop_duplicates(subset=pk_cols, keep="last")
    tmp = f"_tmp_{table}"
    con.register(tmp, df)
    if len(pk_cols) == 1:
        col = pk_cols[0]
        con.execute(f"DELETE FROM {table} WHERE {col} IN (SELECT {col} FROM {tmp})")
    else:
        # Composite PK: build a tuple IN clause
        cols_csv = ", ".join(pk_cols)
        con.execute(
            f"DELETE FROM {table} WHERE ({cols_csv}) IN (SELECT {cols_csv} FROM {tmp})"
        )
    cols = ", ".join(df.columns.tolist())
    con.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM {tmp}")
    con.unregister(tmp)


def load_staging_to_warehouse(
    db_path: Path,
    staging_dir: Path,
) -> None:
    from tikitaka_dwh.transform.dimensions import (
        build_dim_store_from_df,
        build_dim_pos_from_df,
        build_dim_operator_from_df,
        build_dim_product_from_df,
        build_dim_customer_from_df,
    )

    df_docs = _read_parquet_dir(staging_dir, "documents")
    df_lines = _read_parquet_dir(staging_dir, "sale_lines")
    df_pmts = _read_parquet_dir(staging_dir, "payments")

    if df_docs.empty:
        # Fallback: re-transform from raw JSON (first run before staging exists)
        logger.info("No staging Parquet found — falling back to raw JSON transform.")
        from tikitaka_dwh.transform.documents import build_documents
        from tikitaka_dwh.transform.sale_lines import build_sale_lines
        from tikitaka_dwh.transform.payments import build_payments

        raw_docs = _load_all_raw(staging_dir)
        if not raw_docs:
            logger.info("No raw documents found — nothing to load.")
            return
        logger.info("Loading %d raw documents into warehouse …", len(raw_docs))
        df_docs = build_documents(raw_docs)
        df_lines = build_sale_lines(raw_docs)
        df_pmts = build_payments(raw_docs)
    else:
        logger.info("Loading %d document rows from staging Parquet …", len(df_docs))

    con = get_connection(db_path)
    try:
        con.begin()

        _upsert_df(con, df_docs, "fct_documents", ["id"])
        _upsert_df(con, df_lines, "fct_sale_lines", ["doc_id", "row_num"])
        _upsert_df(con, df_pmts, "fct_payments", ["doc_id", "payment_seq"])

        _upsert_df(con, build_dim_store_from_df(df_docs), "dim_store", ["store_number"])
        _upsert_df(con, build_dim_pos_from_df(df_docs), "dim_pos", ["pos_id"])
        _upsert_df(con, build_dim_operator_from_df(df_docs), "dim_operator", ["operator_id"])
        _upsert_df(con, build_dim_product_from_df(df_lines), "dim_product", ["product_code"])
        _upsert_df(con, build_dim_customer_from_df(df_docs), "dim_customer", ["customer_key"])

        _rebuild_aggregates(con)
        con.commit()
        logger.info("Warehouse load complete.")
    except Exception:
        con.rollback()
        logger.error("Warehouse load failed — rolled back.", exc_info=True)
        raise
    finally:
        con.close()


def _read_parquet_dir(staging_dir: Path, table_name: str) -> pd.DataFrame:
    import pyarrow.parquet as pq

    table_dir = staging_dir / table_name
    if not table_dir.exists():
        return pd.DataFrame()
    files = sorted(table_dir.rglob("*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = []
    for f in files:
        try:
            frames.append(pq.ParquetFile(f).read().to_pandas())
        except Exception:
            logger.warning("Failed to read staging Parquet %s", f, exc_info=True)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_all_raw(staging_dir: Path) -> list[dict]:  # type: ignore[type-arg]
    import json

    docs = []
    raw_root = staging_dir.parent / "raw"
    if not raw_root.exists():
        return docs
    for json_file in sorted(raw_root.rglob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                docs.extend(data)
        except Exception:
            logger.warning("Failed to read %s", json_file, exc_info=True)
    return docs


def _rebuild_aggregates(con: duckdb.DuckDBPyConnection) -> None:
    logger.info("Rebuilding aggregates …")

    con.execute("""
        CREATE OR REPLACE TABLE agg_daily_revenue AS
        SELECT
            doc_date,
            store_number,
            pos_id,
            operator_id,
            SUM(doc_sum)          AS gross,
            COUNT(*)              AS txn_count,
            0                     AS item_count
        FROM fct_documents
        WHERE doc_type = 'sale'
        GROUP BY doc_date, store_number, pos_id, operator_id
    """)

    con.execute("""
        CREATE OR REPLACE TABLE agg_product_daily AS
        SELECT
            sl.doc_date,
            sl.product_code,
            SUM(sl.quantity)      AS qty,
            SUM(sl.total_sum)     AS gross,
            COUNT(*)              AS lines
        FROM fct_sale_lines sl
        GROUP BY sl.doc_date, sl.product_code
    """)

    con.execute("""
        CREATE OR REPLACE TABLE agg_hourly AS
        SELECT
            doc_date,
            HOUR(doc_datetime_local) AS hour_of_day,
            store_number,
            COUNT(*)                 AS txn_count,
            SUM(doc_sum)             AS gross
        FROM fct_documents
        WHERE doc_type = 'sale'
        GROUP BY doc_date, HOUR(doc_datetime_local), store_number
    """)

    logger.info("Aggregates rebuilt.")
