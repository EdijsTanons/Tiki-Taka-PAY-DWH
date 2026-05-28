"""Page 3 — Stores & POS."""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from tikitaka_dwh.ui.components import (
    date_store_pos_where,
    error_card,
    query,
)
from tikitaka_dwh.ui.i18n import t


def render() -> None:
    st.title(t("stores_title"))
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning(t("apply_filters"))
        return

    try:
        _render_store_revenue(filters)
        st.divider()
        _render_pos_revenue(filters)
        st.divider()
        _render_operator_leaderboard(filters)
        st.divider()
        _render_comparison(filters)
    except Exception as exc:
        error_card(t("stores_page_error"), exc)


def _render_store_revenue(filters: dict) -> None:
    where, params = date_store_pos_where(filters)
    store_col = t("stores_col_store")
    gross_col = t("stores_col_gross")
    txns_col = t("stores_col_txns")
    avg_col = t("stores_col_avg_basket")
    df = query(
        f"""
        SELECT
            store_number                AS "{store_col}",
            SUM(doc_sum)                AS "{gross_col}",
            COUNT(*)                    AS "{txns_col}",
            AVG(doc_sum)                AS "{avg_col}"
        FROM fct_documents
        WHERE doc_type = 'sale' AND {where}
        GROUP BY store_number
        ORDER BY "{gross_col}" DESC
        """,
        params,
    )
    if df.empty:
        st.info(t("stores_no_data"))
        return
    st.subheader(t("stores_rev_by_store"))
    st.bar_chart(df.set_index(store_col)[gross_col])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_pos_revenue(filters: dict) -> None:
    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT
            fd.pos_id                   AS pos_id,
            dp.device_serial_number     AS serial,
            fd.store_number             AS store,
            SUM(fd.doc_sum)             AS gross,
            COUNT(*)                    AS txns
        FROM fct_documents fd
        LEFT JOIN dim_pos dp ON fd.pos_id = dp.pos_id
        WHERE fd.doc_type = 'sale' AND {where}
        GROUP BY fd.pos_id, dp.device_serial_number, fd.store_number
        ORDER BY gross DESC
        """,
        params,
    )
    if df.empty:
        return
    pos_id_col = t("stores_col_pos_id")
    serial_col = t("stores_col_serial")
    store_col = t("stores_col_store")
    gross_col = t("stores_col_gross")
    txns_col = t("stores_col_txns")
    df.columns = [pos_id_col, serial_col, store_col, gross_col, txns_col]
    st.subheader(t("stores_rev_by_pos"))
    st.bar_chart(df.set_index(pos_id_col)[gross_col])
    st.dataframe(df, use_container_width=True, hide_index=True)

    total = df[gross_col].sum()
    st.caption(t("stores_total", n=total))


def _render_operator_leaderboard(filters: dict) -> None:
    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT
            fd.operator_id              AS op_id,
            do_.operator_name           AS name,
            SUM(fd.doc_sum)             AS gross,
            COUNT(*)                    AS txns,
            AVG(fd.doc_sum)             AS avg_basket
        FROM fct_documents fd
        LEFT JOIN dim_operator do_ ON fd.operator_id = do_.operator_id
        WHERE fd.doc_type = 'sale' AND {where}
        GROUP BY fd.operator_id, do_.operator_name
        ORDER BY gross DESC
        """,
        params,
    )
    if df.empty:
        return
    df.columns = [
        t("stores_col_id"),
        t("stores_col_operator"),
        t("stores_col_gross"),
        t("stores_col_txns"),
        t("stores_col_avg_basket"),
    ]
    st.subheader(t("stores_operator_lb"))
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_comparison(filters: dict) -> None:
    st.subheader(t("stores_period_comp"))
    start = filters["start"]
    end = filters["end"]
    span = (end - start).days + 1

    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)

    c1, c2 = st.columns(2)

    def _period_metrics(label: str, pstart, pend, col) -> None:
        pf = {**filters, "start": pstart, "end": pend}
        where, params = date_store_pos_where(pf)
        df = query(
            f"""
            SELECT SUM(doc_sum) AS gross, COUNT(*) AS txns
            FROM fct_documents
            WHERE doc_type = 'sale' AND {where}
            """,
            params,
        )
        with col:
            st.markdown(f"**{label}**  \n{pstart} → {pend}")
            if not df.empty and not df["gross"].isna().all():
                row = df.iloc[0]
                st.metric(t("stores_gross"), f"€ {row['gross']:,.2f}")
                st.metric(t("stores_col_txns"), f"{int(row['txns']):,}")
            else:
                st.info(t("stores_no_data"))

    _period_metrics(t("stores_current_period"), start, end, c1)
    _period_metrics(t("stores_previous_period"), prev_start, prev_end, c2)
