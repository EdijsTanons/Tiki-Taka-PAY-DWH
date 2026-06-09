"""SCD-1 dimension builders from staging data."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def build_dim_store(raw_docs: Iterable[dict[str, Any]]) -> pd.DataFrame:
    seen: dict[str, dict[str, Any]] = {}
    for doc in raw_docs:
        sn = doc.get("store_number")
        if sn and sn not in seen:
            seen[sn] = {"store_number": sn, "country": "LV"}
    return pd.DataFrame(list(seen.values()))


def build_dim_pos(raw_docs: Iterable[dict[str, Any]]) -> pd.DataFrame:
    seen: dict[int, dict[str, Any]] = {}
    for doc in raw_docs:
        pos_id = doc.get("id_device")
        if pos_id is None:
            continue
        pos_id = int(pos_id)
        serial = doc.get("device_serial_number")
        dt_str = doc.get("doc_datetime")
        ts: Any = None
        if dt_str:
            with contextlib.suppress(Exception):
                ts = datetime.fromisoformat(dt_str)
        if pos_id not in seen:
            seen[pos_id] = {"pos_id": pos_id, "device_serial_number": serial, "first_seen": ts, "last_seen": ts}
        else:
            existing = seen[pos_id]
            if ts and (existing["first_seen"] is None or ts < existing["first_seen"]):
                existing["first_seen"] = ts
            if ts and (existing["last_seen"] is None or ts > existing["last_seen"]):
                existing["last_seen"] = ts
    return pd.DataFrame(list(seen.values()))


def build_dim_operator(raw_docs: Iterable[dict[str, Any]]) -> pd.DataFrame:
    seen: dict[str, dict[str, Any]] = {}
    for doc in raw_docs:
        op_id = doc.get("operator_id")
        if not op_id:
            continue
        dt_str = doc.get("doc_datetime")
        ts: Any = None
        if dt_str:
            with contextlib.suppress(Exception):
                ts = datetime.fromisoformat(dt_str)
        op_name = doc.get("operator_name")
        if op_id not in seen:
            seen[op_id] = {"operator_id": op_id, "operator_name": op_name, "first_seen": ts, "last_seen": ts}
        else:
            existing = seen[op_id]
            if ts and (existing["first_seen"] is None or ts < existing["first_seen"]):
                existing["first_seen"] = ts
            if ts and (existing["last_seen"] is None or ts > existing["last_seen"]):
                existing["last_seen"] = ts
                existing["operator_name"] = op_name  # SCD1: keep latest name
    return pd.DataFrame(list(seen.values()))


def build_dim_product(raw_docs: Iterable[dict[str, Any]]) -> pd.DataFrame:
    seen: dict[str, dict[str, Any]] = {}
    for doc in raw_docs:
        for product in doc.get("sold_products") or []:
            code = product.get("product_code")
            if not code:
                continue
            seen[code] = {
                "product_code": code,
                "product_name": product.get("product_name"),
                "department": product.get("department"),
                "vat_rate": product.get("vat_rate"),
            }
    return pd.DataFrame(list(seen.values()))


def build_dim_customer(raw_docs: Iterable[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for doc in raw_docs:
        card = doc.get("customer_card_number")
        reg = doc.get("client_reg_number")
        if card and card not in seen_keys:
            seen_keys.add(card)
            rows.append({"customer_key": card, "customer_kind": "loyalty", "customer_card_number": card, "client_reg_number": None, "client_title": None})
        if reg and reg not in seen_keys:
            seen_keys.add(reg)
            rows.append({"customer_key": reg, "customer_kind": "b2b", "customer_card_number": None, "client_reg_number": reg, "client_title": doc.get("client_title")})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# DataFrame-based builders (used when staging Parquet is available)
# ---------------------------------------------------------------------------


def build_dim_store_from_df(df_docs: pd.DataFrame) -> pd.DataFrame:
    if df_docs.empty or "store_number" not in df_docs.columns:
        return pd.DataFrame()
    stores = df_docs["store_number"].dropna().unique()
    return pd.DataFrame([{"store_number": sn, "country": "LV"} for sn in stores])


def build_dim_pos_from_df(df_docs: pd.DataFrame) -> pd.DataFrame:
    if df_docs.empty or "pos_id" not in df_docs.columns:
        return pd.DataFrame()
    sub = df_docs[["pos_id", "device_serial_number", "doc_datetime_local"]].copy()
    sub = sub.dropna(subset=["pos_id"])
    sub["ts"] = pd.to_datetime(sub["doc_datetime_local"], errors="coerce")
    result = (
        sub.sort_values("ts")
        .groupby("pos_id")
        .agg(
            device_serial_number=("device_serial_number", "last"),
            first_seen=("ts", "min"),
            last_seen=("ts", "max"),
        )
        .reset_index()
    )
    return result


def build_dim_operator_from_df(df_docs: pd.DataFrame) -> pd.DataFrame:
    if df_docs.empty or "operator_id" not in df_docs.columns:
        return pd.DataFrame()
    cols = ["operator_id", "doc_datetime_local"]
    if "operator_name" in df_docs.columns:
        cols.append("operator_name")
    sub = df_docs[cols].copy()
    sub = sub.dropna(subset=["operator_id"])
    sub["ts"] = pd.to_datetime(sub["doc_datetime_local"], errors="coerce")
    if "operator_name" in sub.columns:
        result = (
            sub.sort_values("ts")
            .groupby("operator_id")
            .agg(
                operator_name=("operator_name", "last"),
                first_seen=("ts", "min"),
                last_seen=("ts", "max"),
            )
            .reset_index()
        )
    else:
        result = (
            sub.groupby("operator_id")
            .agg(first_seen=("ts", "min"), last_seen=("ts", "max"))
            .reset_index()
        )
        result["operator_name"] = None
    return result


def build_dim_product_from_df(df_lines: pd.DataFrame) -> pd.DataFrame:
    if df_lines.empty or "product_code" not in df_lines.columns:
        return pd.DataFrame()
    cols = ["product_code", "product_name", "department", "vat_rate"]
    available = [c for c in cols if c in df_lines.columns]
    sub = df_lines[available].dropna(subset=["product_code"])
    return sub.drop_duplicates(subset=["product_code"], keep="last").reset_index(drop=True)


def build_dim_customer_from_df(df_docs: pd.DataFrame) -> pd.DataFrame:
    if df_docs.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for _, row in df_docs.iterrows():
        card = row.get("customer_card_number")
        reg = row.get("client_reg_number")
        if card and pd.notna(card) and card not in seen_keys:
            seen_keys.add(card)
            rows.append({"customer_key": card, "customer_kind": "loyalty", "customer_card_number": card, "client_reg_number": None, "client_title": None})
        if reg and pd.notna(reg) and reg not in seen_keys:
            seen_keys.add(reg)
            rows.append({"customer_key": reg, "customer_kind": "b2b", "customer_card_number": None, "client_reg_number": reg, "client_title": None})
    return pd.DataFrame(rows)
