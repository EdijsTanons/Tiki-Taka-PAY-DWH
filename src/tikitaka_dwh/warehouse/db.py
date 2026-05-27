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
        # Fallback: no staging Parquet at all (e.g. staging_dir was never written).
        # NOTE: this branch is intentionally not reached when only *some* pages failed
        # staging — that case is prevented upstream by letting staging errors fail the
        # sync so the watermark never advances past un-staged data.
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


# ---------------------------------------------------------------------------
# Raw-JSON audit and rebuild
# ---------------------------------------------------------------------------


def audit_raw(raw_dir: Path) -> dict:  # type: ignore[type-arg]
    """Scan all raw JSON files under *raw_dir* and return deduplication stats.

    Returns a dict with keys:
        files         – number of .json files found
        total_docs    – total document records across all files (with dups)
        unique_ids    – number of distinct doc IDs
        duplicate_docs – total_docs − unique_ids
        min_id        – smallest doc ID (or None)
        max_id        – largest doc ID (or None)
    """
    import json

    files = 0
    total_docs = 0
    seen_ids: set[int] = set()

    for json_file in sorted(raw_dir.rglob("*.json")):
        files += 1
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for doc in data:
                    total_docs += 1
                    doc_id = doc.get("id")
                    if doc_id is not None:
                        seen_ids.add(int(doc_id))
        except Exception:
            logger.warning("audit_raw: could not read %s", json_file, exc_info=True)

    unique_ids = len(seen_ids)
    return {
        "files": files,
        "total_docs": total_docs,
        "unique_ids": unique_ids,
        "duplicate_docs": total_docs - unique_ids,
        "min_id": min(seen_ids) if seen_ids else None,
        "max_id": max(seen_ids) if seen_ids else None,
    }


def rebuild_from_raw(
    db_path: Path,
    raw_dir: Path,
    watermark: "WatermarkStore | None" = None,
    set_watermark: bool = False,
) -> dict:  # type: ignore[type-arg]
    """Load every raw JSON file into the warehouse, deduplicating by doc ID.

    This is useful when:
    * A backfill was interrupted and you want to see whatever data is on disk.
    * You suspect staging Parquet files are out of sync with raw JSON.

    By default the watermark is **not** updated so a pending backfill can
    still resume and fetch the remaining documents.  Pass *set_watermark=True*
    only when you are certain all documents have been downloaded.

    Returns the same stats dict as :func:`audit_raw` plus
    ``warehouse_rows`` (docs inserted/updated).
    """
    import json

    # 1. Collect all docs, keep the last occurrence of each ID
    all_docs: dict[int, dict] = {}  # type: ignore[type-arg]
    total_raw = 0
    files_read = 0

    for json_file in sorted(raw_dir.rglob("*.json")):
        files_read += 1
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for doc in data:
                    total_raw += 1
                    doc_id = doc.get("id")
                    if doc_id is not None:
                        all_docs[int(doc_id)] = doc
        except Exception:
            logger.warning("rebuild_from_raw: could not read %s", json_file, exc_info=True)

    unique = len(all_docs)
    duplicates = total_raw - unique
    logger.info(
        "rebuild_from_raw: %d files, %d total records, %d unique IDs, %d duplicates",
        files_read, total_raw, unique, duplicates,
    )

    if not all_docs:
        logger.info("rebuild_from_raw: no documents found — nothing to load.")
        return {
            "files": files_read, "total_docs": 0, "unique_ids": 0,
            "duplicate_docs": 0, "min_id": None, "max_id": None, "warehouse_rows": 0,
        }

    from tikitaka_dwh.transform.documents import build_documents
    from tikitaka_dwh.transform.sale_lines import build_sale_lines
    from tikitaka_dwh.transform.payments import build_payments
    from tikitaka_dwh.transform.dimensions import (
        build_dim_store_from_df,
        build_dim_pos_from_df,
        build_dim_operator_from_df,
        build_dim_product_from_df,
        build_dim_customer_from_df,
    )

    doc_list = list(all_docs.values())
    df_docs = build_documents(doc_list)
    df_lines = build_sale_lines(doc_list)
    df_pmts = build_payments(doc_list)

    # 2. Load into warehouse
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
        logger.info("rebuild_from_raw: warehouse load complete (%d rows).", unique)
    except Exception:
        con.rollback()
        logger.error("rebuild_from_raw: load failed — rolled back.", exc_info=True)
        raise
    finally:
        con.close()

    # 3. Optionally advance the watermark
    max_id = max(all_docs.keys())
    min_id = min(all_docs.keys())
    if set_watermark and watermark is not None:
        watermark.set_last_seen_id(max_id)
        watermark.mark_sync_completed()
        logger.info("rebuild_from_raw: watermark set to max_id=%d", max_id)

    return {
        "files": files_read,
        "total_docs": total_raw,
        "unique_ids": unique,
        "duplicate_docs": duplicates,
        "min_id": min_id,
        "max_id": max_id,
        "warehouse_rows": unique,
    }


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
