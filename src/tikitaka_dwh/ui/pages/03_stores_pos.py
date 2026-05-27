"""Page 3 — Stores & POS."""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from tikitaka_dwh.ui.components import (
    date_store_pos_where,
    error_card,
    query,
)


def render() -> None:
    st.title("Stores & POS")
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning("Apply filters in the sidebar.")
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
        error_card("Stores & POS page error", exc)


def _render_store_revenue(filters: dict) -> None:
    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT
            store_number                AS "Store",
            SUM(doc_sum)                AS "Gross (€)",
            COUNT(*)                    AS "Transactions",
            AVG(doc_sum)                AS "Avg basket (€)"
        FROM fct_documents
        WHERE doc_type = 'sale' AND {where}
        GROUP BY store_number
        ORDER BY "Gross (€)" DESC
        """,
        params,
    )
    if df.empty:
        st.info("No data.")
        return
    st.subheader("Revenue by store")
    st.bar_chart(df.set_index("Store")["Gross (€)"])
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
    df.columns = ["POS ID", "Serial", "Store", "Gross (€)", "Transactions"]
    st.subheader("Revenue by POS terminal")
    st.bar_chart(df.set_index("POS ID")["Gross (€)"])
    st.dataframe(df, use_container_width=True, hide_index=True)

    total = df["Gross (€)"].sum()
    st.caption(f"Total: € {total:,.2f}")


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
    df.columns = ["ID", "Operator", "Gross (€)", "Transactions", "Avg basket (€)"]
    st.subheader("Operator leaderboard")
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_comparison(filters: dict) -> None:
    st.subheader("Period comparison")
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
                st.metric("Gross", f"€ {row['gross']:,.2f}")
                st.metric("Transactions", f"{int(row['txns']):,}")
            else:
                st.info("No data.")

    _period_metrics("Current period", start, end, c1)
    _period_metrics("Previous period", prev_start, prev_end, c2)
