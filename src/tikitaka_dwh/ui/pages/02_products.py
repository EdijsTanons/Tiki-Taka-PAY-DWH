"""Page 2 — Products."""

from __future__ import annotations

from typing import Any

import streamlit as st

from tikitaka_dwh.ui.components import (
    csv_download_button,
    date_store_pos_where,
    error_card,
    excel_download_button,
    query,
)
from tikitaka_dwh.ui.i18n import t


def render() -> None:
    st.title(t("prod_title"))
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning(t("apply_filters"))
        return

    try:
        _render_top_n(filters)
        st.divider()
        _render_department_breakdown(filters)
        st.divider()
        _render_product_table(filters)
        st.divider()
        _render_daily_product_report(filters)
    except Exception as exc:
        error_card(t("prod_page_error"), exc)


def _render_top_n(filters: dict[str, Any]) -> None:
    rank_revenue = t("prod_rank_revenue")
    rank_qty = t("prod_rank_qty")

    col_sort, col_n = st.columns([3, 1])
    with col_sort:
        sort_by = st.radio(t("prod_rank_by"), [rank_revenue, rank_qty], horizontal=True, key="prod_sort")
    with col_n:
        top_n = st.selectbox(t("prod_top_n"), [10, 20, 50], key="prod_topn")

    order_col = "gross" if sort_by == rank_revenue else "qty"
    where, params = date_store_pos_where(filters, alias="fd")
    df = query(
        f"""
        SELECT
            sl.product_code                 AS "Product code",
            sl.product_name                 AS "Product",
            sl.department                   AS "Department",
            SUM(sl.quantity)                AS qty,
            SUM(sl.total_sum)               AS gross,
            COUNT(*)                        AS lines
        FROM fct_sale_lines sl
        JOIN fct_documents fd ON sl.doc_id = fd.id
        WHERE {where}
        GROUP BY sl.product_code, sl.product_name, sl.department
        ORDER BY {order_col} DESC
        LIMIT {int(top_n)}
        """,
        params,
    )
    if df.empty:
        st.info(t("prod_no_data"))
        return

    label = t("prod_top_label", n=top_n, sort=sort_by.lower())
    st.subheader(label)

    prod_col = t("prod_col_product")
    dept_col = t("prod_col_dept")
    qty_col = t("prod_col_qty")
    rev_col = t("prod_col_revenue")

    display = df[["Product", "Department", "qty", "gross"]].copy()
    display.columns = [prod_col, dept_col, qty_col, rev_col]
    st.bar_chart(
        display.set_index(prod_col)[rev_col]
        if sort_by == rank_revenue
        else display.set_index(prod_col)[qty_col]
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def _render_department_breakdown(filters: dict[str, Any]) -> None:
    where, params = date_store_pos_where(filters, alias="fd")
    df = query(
        f"""
        SELECT
            sl.department           AS department,
            SUM(sl.total_sum)       AS gross
        FROM fct_sale_lines sl
        JOIN fct_documents fd ON sl.doc_id = fd.id
        WHERE {where} AND sl.department IS NOT NULL
        GROUP BY sl.department
        ORDER BY gross DESC
        """,
        params,
    )
    if df.empty:
        return
    st.subheader(t("prod_dept_chart"))
    st.bar_chart(df.set_index("department")["gross"])


def _render_product_table(filters: dict[str, Any]) -> None:
    st.subheader(t("prod_search_section"))
    search = st.text_input(t("prod_search_input"), key="prod_search")
    where, params = date_store_pos_where(filters, alias="fd")

    search_clause = ""
    if search:
        search_clause = "AND (LOWER(sl.product_name) LIKE ? OR LOWER(sl.product_code) LIKE ?)"
        params = [*params, f"%{search.lower()}%", f"%{search.lower()}%"]

    code_col = t("prod_col_code")
    prod_col = t("prod_col_product")
    dept_col = t("prod_col_dept")
    qty_col = t("prod_col_qty")
    rev_col = t("prod_col_revenue")
    avg_col = t("prod_col_avg_price")
    lines_col = t("prod_col_lines")

    df = query(
        f"""
        SELECT
            sl.product_code     AS "{code_col}",
            sl.product_name     AS "{prod_col}",
            sl.department       AS "{dept_col}",
            SUM(sl.quantity)    AS "{qty_col}",
            SUM(sl.total_sum)   AS "{rev_col}",
            AVG(sl.price)       AS "{avg_col}",
            COUNT(*)            AS "{lines_col}"
        FROM fct_sale_lines sl
        JOIN fct_documents fd ON sl.doc_id = fd.id
        WHERE {where} {search_clause}
        GROUP BY sl.product_code, sl.product_name, sl.department
        ORDER BY 5 DESC  -- revenue; positional because column aliases are translated
        """,
        params,
    )
    if df.empty:
        st.info(t("prod_no_match"))
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv_download_button(df, "products.csv")


def _render_daily_product_report(filters: dict[str, Any]) -> None:
    st.subheader(t("prod_daily_section"))
    where, params = date_store_pos_where(filters, alias="fd")

    date_col = t("prod_col_date")
    code_col = t("prod_col_code")
    prod_col = t("prod_col_product")
    dept_col = t("prod_col_dept")
    qty_col = t("prod_col_qty")
    rev_col = t("prod_col_revenue")
    avg_col = t("prod_col_avg_price")
    lines_col = t("prod_col_lines")

    df = query(
        f"""
        SELECT
            sl.doc_date             AS "{date_col}",
            sl.product_code         AS "{code_col}",
            sl.product_name         AS "{prod_col}",
            sl.department           AS "{dept_col}",
            SUM(sl.quantity)        AS "{qty_col}",
            SUM(sl.total_sum)       AS "{rev_col}",
            AVG(sl.price)           AS "{avg_col}",
            COUNT(*)                AS "{lines_col}"
        FROM fct_sale_lines sl
        JOIN fct_documents fd ON sl.doc_id = fd.id
        WHERE {where}
        GROUP BY sl.doc_date, sl.product_code, sl.product_name, sl.department
        ORDER BY 1 DESC, 6 DESC  -- date, revenue; positional because aliases are translated
        """,
        params,
    )
    if df.empty:
        st.info(t("prod_no_period_data"))
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    col1, col2 = st.columns(2)
    with col1:
        csv_download_button(df, "products_by_day.csv")
    with col2:
        excel_download_button(df, "products_by_day.xlsx")
