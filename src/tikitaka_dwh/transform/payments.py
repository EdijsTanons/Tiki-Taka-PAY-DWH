"""Build fct_payments from raw API dicts."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _mask_pan(pan: str | None) -> str | None:
    if not pan:
        return None
    digits = pan.replace(" ", "").replace("-", "")
    return "*" * max(0, len(digits) - 4) + digits[-4:]


def build_payments(raw_docs: Iterable[dict[str, Any]]) -> pd.DataFrame:
    rows = []

    for doc in raw_docs:
        doc_id = doc.get("id")
        doc_date_str = doc.get("doc_datetime")
        doc_date: Any | None = None
        if doc_date_str:
            try:
                from datetime import datetime
                doc_date = datetime.fromisoformat(doc_date_str).date()
            except Exception:
                pass

        payments: list[dict[str, Any]] = doc.get("payments") or []

        if not payments:
            # Some docs store payment info at the top level
            top_amount = doc.get("doc_sum")
            if top_amount and doc.get("payment_type"):
                payments = [
                    {
                        "payment_type": doc.get("payment_type"),
                        "payment_method": doc.get("payment_method"),
                        "amount": top_amount,
                        "card_type": doc.get("card_type"),
                        "card_pan": doc.get("card_pan"),
                        "card_tid": doc.get("card_tid"),
                        "card_reference_number": doc.get("card_reference_number"),
                        "gift_card_number": doc.get("gift_card_number"),
                    }
                ]

        for seq, pmt in enumerate(payments):
            rows.append(
                {
                    "doc_id": doc_id,
                    "payment_seq": seq,
                    "payment_type": pmt.get("payment_type"),
                    "payment_method": pmt.get("payment_method"),
                    "amount": pmt.get("amount"),
                    "card_type": pmt.get("card_type"),
                    "card_pan_masked": _mask_pan(pmt.get("card_pan")),
                    "card_tid": pmt.get("card_tid"),
                    "card_reference_number": pmt.get("card_reference_number"),
                    "gift_card_number": pmt.get("gift_card_number"),
                    "doc_date": doc_date,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["doc_id"] = pd.to_numeric(df["doc_id"], errors="coerce").astype("Int64")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    return df


def write_payments_staging(
    df: pd.DataFrame,
    staging_dir: Path,
    run_id: str,
    seq: int = 0,
) -> None:
    if df.empty:
        return
    for date_val, group in df.groupby("doc_date"):
        date_str = str(date_val) if date_val else "unknown"
        part_dir = staging_dir / "payments" / f"dt={date_str}"
        part_dir.mkdir(parents=True, exist_ok=True)
        out = part_dir / f"part-{run_id}-{seq:04d}.parquet"
        group.to_parquet(out, index=False)
        logger.debug("Wrote %d payment rows to %s", len(group), out)
