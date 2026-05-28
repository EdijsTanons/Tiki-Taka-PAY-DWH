"""Page 5 — VAT summary."""

from __future__ import annotations

import streamlit as st

from tikitaka_dwh.ui.components import (
    date_store_pos_where,
    error_card,
    excel_download_button,
    query,
)
from tikitaka_dwh.ui.i18n import t


def render() -> None:
    st.title(t("vat_title"))
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning(t("apply_filters"))
        return

    try:
        _render_vat_table(filters)
        st.divider()
        _render_reconciliation(filters)
    except Exception as exc:
        error_card(t("vat_page_error"), exc)


def _render_vat_table(filters: dict) -> None:
    where, params = date_store_pos_where(filters, alias="fd")

    rate_title_col = t("vat_col_rate_title")
    rate_pct_col = t("vat_col_rate_pct")
    net_col = t("vat_col_net")
    vat_col = t("vat_col_vat")
    gross_col = t("vat_col_gross")
    lines_col = t("vat_col_lines")

    df = query(
        f"""
        SELECT
            sl.vat_title                AS "{rate_title_col}",
            sl.vat_rate                 AS "{rate_pct_col}",
            SUM(sl.sum_without_vat)     AS "{net_col}",
            SUM(sl.vat_sum)             AS "{vat_col}",
            SUM(sl.total_sum)           AS "{gross_col}",
            COUNT(*)                    AS "{lines_col}"
        FROM fct_sale_lines sl
        JOIN fct_documents fd ON sl.doc_id = fd.id
        WHERE {where}
          AND sl.vat_title IS NOT NULL
        GROUP BY sl.vat_title, sl.vat_rate
        ORDER BY sl.vat_rate DESC NULLS LAST
        """,
        params,
    )
    if df.empty:
        st.info(t("vat_no_data"))
        return

    st.subheader(t("vat_by_rate"))
    totals = {
        rate_title_col: t("vat_total_row"),
        rate_pct_col: "",
        net_col: df[net_col].sum(),
        vat_col: df[vat_col].sum(),
        gross_col: df[gross_col].sum(),
        lines_col: df[lines_col].sum(),
    }
    import pandas as pd
    display = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
    st.dataframe(display, use_container_width=True, hide_index=True)
    excel_download_button(df, "vat_summary.xlsx", t("vat_export_excel"))


def _render_reconciliation(filters: dict) -> None:
    where_fd, params_fd = date_store_pos_where(filters)
    where_sl, params_sl = date_store_pos_where(filters, alias="fd")

    doc_total = query(
        f"""
        SELECT SUM(doc_sum) AS total
        FROM fct_documents
        WHERE doc_type = 'sale' AND {where_fd}
        """,
        params_fd,
    )
    line_total = query(
        f"""
        SELECT SUM(sl.total_sum) AS total
        FROM fct_sale_lines sl
        JOIN fct_documents fd ON sl.doc_id = fd.id
        WHERE {where_sl}
        """,
        params_sl,
    )

    if doc_total.empty or line_total.empty:
        return

    dt = doc_total["total"].iloc[0] or 0.0
    lt = line_total["total"].iloc[0] or 0.0
    diff = abs(dt - lt)

    st.subheader(t("vat_reconciliation"))
    c1, c2, c3 = st.columns(3)
    c1.metric(t("vat_recon_doc_total"), f"€ {dt:,.2f}")
    c2.metric(t("vat_recon_line_total"), f"€ {lt:,.2f}")
    if diff <= 0.02:
        c3.metric(t("vat_recon_diff"), f"€ {diff:,.4f}", delta="✓ within tolerance", delta_color="normal")
    else:
        c3.metric(t("vat_recon_diff"), f"€ {diff:,.4f}", delta=f"⚠ exceeds €0.02", delta_color="inverse")
