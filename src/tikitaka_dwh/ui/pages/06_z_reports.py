"""Page 6 — Z Reports: end-of-day summary."""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from tikitaka_dwh.transform.decode import extract_z_report_data
from tikitaka_dwh.ui.components import (
    csv_download_button,
    date_store_pos_where,
    error_card,
    excel_download_button,
    query,
)
from tikitaka_dwh.ui.i18n import t


def render() -> None:
    st.title(t("zr_title"))
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning(t("apply_filters"))
        return
    try:
        _render_page(filters)
    except Exception as exc:
        error_card(t("zr_page_error"), exc)


def _render_page(filters: dict[str, Any]) -> None:
    z_where, z_params = date_store_pos_where(filters, alias="z")
    s_where, s_params = date_store_pos_where(filters, alias="s")

    df = query(
        f"""
        SELECT
            z.id                            AS z_doc_id,
            z.doc_date,
            z.store_number,
            z.pos_id,
            z.doc_num                       AS z_num,
            z.operator_id,
            z.operator_name,
            z.raw_xml,
            COUNT(s.id)                     AS sale_count,
            COALESCE(SUM(s.doc_sum), 0)     AS sales_total
        FROM fct_documents z
        LEFT JOIN fct_documents s
               ON s.doc_date     = z.doc_date
              AND s.store_number = z.store_number
              AND s.pos_id       = z.pos_id
              AND s.doc_type     = 'sale'
        WHERE z.doc_type = 'z_report'
          AND {z_where}
        GROUP BY z.id, z.doc_date, z.store_number, z.pos_id,
                 z.doc_num, z.operator_id, z.operator_name, z.raw_xml
        ORDER BY z.doc_date DESC, z.store_number, z.pos_id
        """,
        z_params,
    )

    if df.empty:
        st.info(t("zr_no_data"))
        return

    parsed = df["raw_xml"].apply(lambda x: extract_z_report_data(x or ""))
    df["z_total"]           = parsed.apply(lambda p: p["total"])
    df["cancelled_count"]   = parsed.apply(lambda p: p["cancelled_count"])
    df["cancelled_amount"]  = parsed.apply(lambda p: p["cancelled_amount"])
    df["refund_count"]      = parsed.apply(lambda p: p["refund_count"])
    df["cash_in"]           = parsed.apply(lambda p: p["cash_in"])
    df["cash_out"]          = parsed.apply(lambda p: p["cash_out"])
    df["vat_rows"]          = parsed.apply(lambda p: p["vat_rows"])

    df["sales_total"] = df["sales_total"].astype(float)

    def _match_flag(row: pd.Series) -> str:
        if row["z_total"] is None:
            return "?"
        return "✓" if abs(row["z_total"] - row["sales_total"]) <= 0.01 else "✗"

    df["match"] = df.apply(_match_flag, axis=1)

    # ── KPI row ────────────────────────────────────────────────────────────────
    total_revenue = float(df["sales_total"].sum())
    days_covered  = int(df["doc_date"].nunique())
    avg_daily     = total_revenue / days_covered if days_covered else 0.0
    cancelled_ttl = int(df["cancelled_count"].fillna(0).astype(int).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("zr_kpi_count"),       len(df))
    c2.metric(t("zr_kpi_total_sales"), f"€{total_revenue:,.2f}")
    c3.metric(t("zr_kpi_avg_daily"),   f"€{avg_daily:,.2f}")
    c4.metric(t("zr_kpi_voided"),      cancelled_ttl)

    st.divider()

    # ── Daily revenue chart ────────────────────────────────────────────────────
    daily = df.groupby("doc_date", as_index=False).agg(gross=("sales_total", "sum"))
    daily["doc_date"] = daily["doc_date"].astype(str)

    chart = (
        alt.Chart(daily)
        .mark_bar(color="#4C8BF5")
        .encode(
            x=alt.X("doc_date:O", title=t("zr_chart_date_axis"), axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("gross:Q", title=t("zr_chart_sales_axis")),
            tooltip=[
                alt.Tooltip("doc_date:O", title=t("zr_chart_date_axis")),
                alt.Tooltip("gross:Q",    title=t("zr_chart_sales_axis"), format=",.2f"),
            ],
        )
        .properties(height=240)
    )
    st.subheader(t("zr_daily_chart"))
    st.altair_chart(chart, use_container_width=True)

    st.divider()

    # ── Z Report register table ────────────────────────────────────────────────
    st.subheader(t("zr_register"))

    with st.expander(t("zr_match_expander")):
        st.markdown(t("zr_match_info"))

    display = df[[
        "doc_date", "store_number", "pos_id", "z_num",
        "operator_id", "operator_name",
        "sale_count", "sales_total", "z_total",
        "match",
        "cancelled_count", "cancelled_amount",
        "refund_count", "cash_in", "cash_out",
    ]].copy()
    display.columns = [
        t("zr_col_date"), t("zr_col_store"), t("zr_col_pos"), t("zr_col_znum"),
        t("zr_col_op_id"), t("zr_col_operator"),
        t("zr_col_txns"), t("zr_col_calculated"), t("zr_col_z_stated"),
        t("zr_col_match"),
        t("zr_col_voided_n"), t("zr_col_voided_eur"),
        t("zr_col_refunds_n"), t("zr_col_cash_in"), t("zr_col_cash_out"),
    ]

    match_col = t("zr_col_match")

    def _style_match(val: object) -> str:
        if val == "✗":
            return "background-color: #ffcccc"
        if val == "✓":
            return "background-color: #ccffcc"
        return ""

    st.dataframe(
        display.style.map(_style_match, subset=[match_col]),
        use_container_width=True,
        hide_index=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        csv_download_button(display, "z_reports.csv")
    with col2:
        excel_download_button(display, "z_reports.xlsx")

    st.divider()

    # ── VAT summary ────────────────────────────────────────────────────────────
    vat_rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        for vr in row["vat_rows"]:
            vat_rows.append({
                t("zr_vat_col_code"):    vr["code"],
                t("zr_vat_col_rate"):    vr["rate"],
                t("zr_vat_col_taxable"): vr["taxable"],
                t("zr_vat_col_vat"):     vr["vat"],
            })

    if vat_rows:
        code_col    = t("zr_vat_col_code")
        rate_col    = t("zr_vat_col_rate")
        taxable_col = t("zr_vat_col_taxable")
        vat_col_lbl = t("zr_vat_col_vat")

        vat_df = pd.DataFrame(vat_rows)
        vat_summary = (
            vat_df.groupby([code_col, rate_col], as_index=False)
            .agg({taxable_col: "sum", vat_col_lbl: "sum"})
            .sort_values(code_col)
        )
        st.subheader(t("zr_vat_section"))
        st.dataframe(vat_summary, use_container_width=True, hide_index=True)
        st.divider()

    # ── Gaps: sales days with no Z report ─────────────────────────────────────
    gaps_df = query(
        f"""
        SELECT s.doc_date, s.store_number, s.pos_id,
               COUNT(*)       AS sale_count,
               SUM(s.doc_sum) AS sales_total
        FROM fct_documents s
        WHERE s.doc_type = 'sale'
          AND {s_where}
          AND NOT EXISTS (
              SELECT 1 FROM fct_documents z2
              WHERE z2.doc_type    = 'z_report'
                AND z2.doc_date     = s.doc_date
                AND z2.store_number = s.store_number
                AND z2.pos_id       = s.pos_id
          )
        GROUP BY s.doc_date, s.store_number, s.pos_id
        ORDER BY s.doc_date DESC
        """,
        s_params,
    )

    if not gaps_df.empty:
        st.subheader(t("zr_gaps_heading", n=len(gaps_df)))
        gaps_df.columns = [
            t("zr_gaps_col_date"), t("zr_gaps_col_store"), t("zr_gaps_col_pos"),
            t("zr_gaps_col_txns"), t("zr_gaps_col_sales"),
        ]
        st.dataframe(gaps_df, use_container_width=True, hide_index=True)
    else:
        st.success(t("zr_all_ok"))
