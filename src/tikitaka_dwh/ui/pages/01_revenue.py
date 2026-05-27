"""Page 1 — Revenue overview."""

from __future__ import annotations

import streamlit as st

from tikitaka_dwh.ui.components import (
    csv_download_button,
    date_store_pos_where,
    error_card,
    query,
)


def render() -> None:
    st.title("Revenue")
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning("Apply filters in the sidebar.")
        return

    try:
        _render_metrics(filters)
        st.divider()
        _render_daily_chart(filters)
        st.divider()
        _render_weekly_bar(filters)
        st.divider()
        _render_table(filters)
    except Exception as exc:
        error_card("Revenue page error", exc)


def _render_metrics(filters: dict) -> None:
    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT
            SUM(doc_sum)                            AS gross,
            SUM(doc_sum) - SUM(
                COALESCE((
                    SELECT SUM(vat_sum)
                    FROM fct_sale_lines sl
                    WHERE sl.doc_id = fd.id
                ), 0)
            )                                       AS net,
            COUNT(*)                                AS txn_count,
            AVG(doc_sum)                            AS avg_basket
        FROM fct_documents fd
        WHERE doc_type = 'sale'
          AND {where}
        """,
        params,
    )

    if df.empty or df["gross"].isna().all():
        st.info("No revenue data for the selected period.")
        return

    row = df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gross revenue", f"€ {row['gross']:,.2f}")
    c2.metric("Net revenue", f"€ {row['net']:,.2f}" if row["net"] else "—")
    c3.metric("Transactions", f"{int(row['txn_count']):,}")
    c4.metric("Avg basket", f"€ {row['avg_basket']:,.2f}" if row["avg_basket"] else "—")


def _render_daily_chart(filters: dict) -> None:
    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT doc_date, SUM(doc_sum) AS gross
        FROM fct_documents
        WHERE doc_type = 'sale' AND {where}
        GROUP BY doc_date
        ORDER BY doc_date
        """,
        params,
    )
    if df.empty:
        return
    st.subheader("Daily revenue")
    st.line_chart(df.set_index("doc_date")["gross"])


def _render_weekly_bar(filters: dict) -> None:
    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT
            DATE_TRUNC('week', doc_date)    AS week_start,
            SUM(doc_sum)                    AS gross
        FROM fct_documents
        WHERE doc_type = 'sale' AND {where}
        GROUP BY week_start
        ORDER BY week_start
        """,
        params,
    )
    if df.empty:
        return
    st.subheader("Weekly revenue")
    st.bar_chart(df.set_index("week_start")["gross"])


def _render_table(filters: dict) -> None:
    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT
            doc_date        AS "Date",
            store_number    AS "Store",
            SUM(doc_sum)    AS "Gross (€)",
            COUNT(*)        AS "Transactions"
        FROM fct_documents
        WHERE doc_type = 'sale' AND {where}
        GROUP BY doc_date, store_number
        ORDER BY doc_date DESC, store_number
        """,
        params,
    )
    if df.empty:
        return
    st.subheader("Daily breakdown")
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv_download_button(df, "revenue.csv")
