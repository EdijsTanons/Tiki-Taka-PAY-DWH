"""Build fct_documents from raw API dicts."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytz

from tikitaka_dwh.transform.decode import decode_text, extract_dok_veids, normalize_doc_type

logger = logging.getLogger(__name__)

_RIGA = pytz.timezone("Europe/Riga")


def _to_utc(local_str: str | None) -> datetime | None:
    if not local_str:
        return None
    try:
        naive = datetime.fromisoformat(local_str)
        # is_dst=False instead of None: during the autumn DST fold the
        # ambiguous hour resolves deterministically to winter time and the
        # spring gap never raises — otherwise those documents would get a
        # doc_date but a NULL doc_datetime_utc twice a year.
        aware: datetime = _RIGA.localize(naive, is_dst=False)
        return aware.astimezone(UTC).replace(tzinfo=None)
    except Exception:
        return None


def build_documents(
    raw_docs: Iterable[dict[str, Any]],
    ingested_at: datetime | None = None,
) -> pd.DataFrame:
    ts = ingested_at or datetime.now(UTC).replace(tzinfo=None)
    rows = []
    for doc in raw_docs:
        doc_datetime_local = doc.get("doc_datetime")
        doc_datetime_utc = _to_utc(doc_datetime_local)
        doc_date = (
            datetime.fromisoformat(doc_datetime_local).date() if doc_datetime_local else None
        )

        raw_xml = doc.get("doc") or ""
        dok_veids_raw = extract_dok_veids(raw_xml) or doc.get("dok_operation") or ""
        doc_type_raw = decode_text(dok_veids_raw) if dok_veids_raw else ""
        doc_type = normalize_doc_type(doc_type_raw) if doc_type_raw else "unknown"

        rows.append(
            {
                "id": doc.get("id"),
                "doc_uid": doc.get("doc_uid"),
                "doc_num": doc.get("doc_num"),
                "doc_datetime_local": doc_datetime_local,
                "doc_datetime_utc": doc_datetime_utc,
                "doc_date": doc_date,
                "doc_type": doc_type,
                "doc_type_raw": doc_type_raw,
                "dok_operation": doc.get("dok_operation"),
                "store_number": doc.get("store_number"),
                "pos_id": doc.get("id_device"),
                "operator_id": doc.get("operator_id"),
                "operator_name": doc.get("operator_name"),
                "doc_sum": doc.get("doc_sum"),
                "currency": doc.get("currency"),
                "non_fiscal": doc.get("non_fiscal"),
                "doc_sha": doc.get("doc_sha"),
                "device_serial_number": doc.get("device_serial_number"),
                "customer_card_number": doc.get("customer_card_number"),
                "client_reg_number": doc.get("client_reg_number"),
                "raw_xml": raw_xml,
                "ingested_at": ts,
                "source_rev": 1,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    df["doc_uid"] = pd.to_numeric(df["doc_uid"], errors="coerce").astype("Int64")
    df["doc_num"] = pd.to_numeric(df["doc_num"], errors="coerce").astype("Int64")
    df["pos_id"] = pd.to_numeric(df["pos_id"], errors="coerce").astype("Int64")
    df["doc_sum"] = pd.to_numeric(df["doc_sum"], errors="coerce")
    df["non_fiscal"] = df["non_fiscal"].astype("boolean")
    return df


def write_documents_staging(
    df: pd.DataFrame,
    staging_dir: Path,
    run_id: str,
    seq: int = 0,
) -> None:
    if df.empty:
        return
    for date_val, group in df.groupby("doc_date"):
        date_str = str(date_val) if date_val else "unknown"
        part_dir = staging_dir / "documents" / f"dt={date_str}"
        part_dir.mkdir(parents=True, exist_ok=True)
        out = part_dir / f"part-{run_id}-{seq:04d}.parquet"
        group.to_parquet(out, index=False)
        logger.debug("Wrote %d document rows to %s", len(group), out)
