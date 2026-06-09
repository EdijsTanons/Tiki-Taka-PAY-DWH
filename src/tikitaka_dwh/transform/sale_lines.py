"""Build fct_sale_lines from raw API dicts."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from tikitaka_dwh.transform.decode import decode_text, extract_dok_veids, normalize_doc_type

logger = logging.getLogger(__name__)

_TOLERANCE = 0.02


def build_sale_lines(raw_docs: Iterable[dict[str, Any]]) -> pd.DataFrame:
    rows = []

    for doc in raw_docs:
        raw_xml = doc.get("doc") or ""
        dok_veids_raw = extract_dok_veids(raw_xml) or doc.get("dok_operation") or ""
        doc_type_raw = decode_text(dok_veids_raw) if dok_veids_raw else ""
        doc_type = normalize_doc_type(doc_type_raw)

        if doc_type != "sale":
            continue

        doc_id = doc.get("id")
        doc_sum = doc.get("doc_sum")
        doc_date_str = doc.get("doc_datetime")
        doc_date: Any | None = None
        if doc_date_str:
            try:
                from datetime import datetime
                doc_date = datetime.fromisoformat(doc_date_str).date()
            except Exception:
                pass

        sold = doc.get("sold_products") or []
        line_total = 0.0

        for idx, product in enumerate(sold):
            discount = (product.get("discount") or 0.0) + (product.get("product_discount") or 0.0)
            total_sum = product.get("total_sum")
            if total_sum is not None:
                line_total += float(total_sum)

            rows.append(
                {
                    "doc_id": doc_id,
                    "row_num": idx,
                    "product_code": product.get("product_code"),
                    "product_name": product.get("product_name"),
                    "department": product.get("department"),
                    "quantity": product.get("quantity"),
                    "unit": product.get("unit"),
                    "price": product.get("price"),
                    "product_sum": product.get("product_sum"),
                    "discount_amount": discount if discount else None,
                    "discount_type": product.get("discount_type"),
                    "excise": product.get("excise"),
                    "sum_without_vat": product.get("sum_without_vat"),
                    "vat_sum": product.get("vat_sum"),
                    "vat_rate": product.get("vat_rate"),
                    "vat_title": product.get("vat_title"),
                    "total_sum": total_sum,
                    "row_type": product.get("row_type"),
                    "pos_code": product.get("pos_code"),
                    "doc_date": doc_date,
                }
            )

        if doc_sum is not None and abs(line_total - float(doc_sum)) > _TOLERANCE:
            logger.warning(
                "Line total reconciliation mismatch for doc_id=%s: lines=%.2f doc_sum=%.2f",
                doc_id,
                line_total,
                doc_sum,
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["doc_id"] = pd.to_numeric(df["doc_id"], errors="coerce").astype("Int64")
    for col in ("quantity", "price", "product_sum", "discount_amount", "excise",
                "sum_without_vat", "vat_sum", "vat_rate", "total_sum"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def write_sale_lines_staging(
    df: pd.DataFrame,
    staging_dir: Path,
    run_id: str,
    seq: int = 0,
) -> None:
    if df.empty:
        return
    for date_val, group in df.groupby("doc_date"):
        date_str = str(date_val) if date_val else "unknown"
        part_dir = staging_dir / "sale_lines" / f"dt={date_str}"
        part_dir.mkdir(parents=True, exist_ok=True)
        out = part_dir / f"part-{run_id}-{seq:04d}.parquet"
        group.to_parquet(out, index=False)
        logger.debug("Wrote %d sale_line rows to %s", len(group), out)
