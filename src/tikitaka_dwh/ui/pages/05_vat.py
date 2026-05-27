"""Page 5 — VAT summary."""

from __future__ import annotations

import streamlit as st

from tikitaka_dwh.ui.components import (
    date_store_pos_where,
    error_card,
    excel_download_button,
    query,
)


def render() -> None:
    st.title("VAT Summary")
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning("Apply filters in the sidebar.")
        return

    try:
        _render_vat_table(filters)
        st.divider()
        _render_reconciliation(filters)
    except Exception as exc:
        error_card("VAT page error", exc)


def _render_vat_table(filters: dict) -> None:
    where, params = date_store_pos_where(filters, alias="fd")
    df = query(
        f"""
        SELECT
            sl.vat_title                AS "VAT rate",
            sl.vat_rate                 AS "Rate (%)",
            SUM(sl.sum_without_vat)     AS "Net (€)",
            SUM(sl.vat_sum)             AS "VAT (€)",
            SUM(sl.total_sum)           AS "Gross (€)",
            COUNT(*)                    AS "Lines"
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
        st.info("No VAT data for the selected period.")
        return

    st.subheader("VAT by rate")
    totals = {
        "VAT rate": "**Total**",
        "Rate (%)": "",
        "Net (€)": df["Net (€)"].sum(),
        "VAT (€)": df["VAT (€)"].sum(),
        "Gross (€)": df["Gross (€)"].sum(),
        "Lines": df["Lines"].sum(),
    }
    import pandas as pd
    display = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
    st.dataframe(display, use_container_width=True, hide_index=True)
    excel_download_button(df, "vat_summary.xlsx", "Export to Excel")


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

    st.subheader("VAT reconciliation")
    c1, c2, c3 = st.columns(3)
    c1.metric("doc_sum total", f"€ {dt:,.2f}")
    c2.metric("Line items total", f"€ {lt:,.2f}")
    if diff <= 0.02:
        c3.metric("Difference", f"€ {diff:,.4f}", delta="✓ within tolerance", delta_color="normal")
    else:
        c3.metric("Difference", f"€ {diff:,.4f}", delta=f"⚠ exceeds €0.02", delta_color="inverse")
