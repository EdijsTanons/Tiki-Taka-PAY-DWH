"""Page 2 — Products."""

from __future__ import annotations

import streamlit as st

from tikitaka_dwh.ui.components import (
    csv_download_button,
    excel_download_button,
    date_store_pos_where,
    error_card,
    query,
)


def render() -> None:
    st.title("Products")
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning("Apply filters in the sidebar.")
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
        error_card("Products page error", exc)


def _render_top_n(filters: dict) -> None:
    col_sort, col_n = st.columns([3, 1])
    with col_sort:
        sort_by = st.radio("Rank by", ["Revenue", "Quantity"], horizontal=True, key="prod_sort")
    with col_n:
        top_n = st.selectbox("Top N", [10, 20, 50], key="prod_topn")

    order_col = "gross" if sort_by == "Revenue" else "qty"
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
        st.info("No product data for the selected period.")
        return

    label = f"Top {top_n} products by {sort_by.lower()}"
    st.subheader(label)
    display = df[["Product", "Department", "qty", "gross"]].copy()
    display.columns = ["Product", "Department", "Qty", "Revenue (€)"]
    st.bar_chart(display.set_index("Product")["Revenue (€)"] if sort_by == "Revenue" else display.set_index("Product")["Qty"])
    st.dataframe(display, use_container_width=True, hide_index=True)


def _render_department_breakdown(filters: dict) -> None:
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
    st.subheader("Revenue by department")
    st.bar_chart(df.set_index("department")["gross"])


def _render_product_table(filters: dict) -> None:
    st.subheader("Product search")
    search = st.text_input("Search product name or code", key="prod_search")
    where, params = date_store_pos_where(filters, alias="fd")

    search_clause = ""
    if search:
        search_clause = "AND (LOWER(sl.product_name) LIKE ? OR LOWER(sl.product_code) LIKE ?)"
        params = params + [f"%{search.lower()}%", f"%{search.lower()}%"]

    df = query(
        f"""
        SELECT
            sl.product_code     AS "Code",
            sl.product_name     AS "Product",
            sl.department       AS "Department",
            SUM(sl.quantity)    AS "Qty",
            SUM(sl.total_sum)   AS "Revenue (€)",
            AVG(sl.price)       AS "Avg price (€)",
            COUNT(*)            AS "Lines"
        FROM fct_sale_lines sl
        JOIN fct_documents fd ON sl.doc_id = fd.id
        WHERE {where} {search_clause}
        GROUP BY sl.product_code, sl.product_name, sl.department
        ORDER BY "Revenue (€)" DESC
        """,
        params,
    )
    if df.empty:
        st.info("No products match.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv_download_button(df, "products.csv")


def _render_daily_product_report(filters: dict) -> None:
    st.subheader("Sold products by day")
    where, params = date_store_pos_where(filters, alias="fd")
    df = query(
        f"""
        SELECT
            sl.doc_date             AS "Date",
            sl.product_code         AS "Code",
            sl.product_name         AS "Product",
            sl.department           AS "Department",
            SUM(sl.quantity)        AS "Qty",
            SUM(sl.total_sum)       AS "Revenue (€)",
            AVG(sl.price)           AS "Avg price (€)",
            COUNT(*)                AS "Lines"
        FROM fct_sale_lines sl
        JOIN fct_documents fd ON sl.doc_id = fd.id
        WHERE {where}
        GROUP BY sl.doc_date, sl.product_code, sl.product_name, sl.department
        ORDER BY sl.doc_date DESC, "Revenue (€)" DESC
        """,
        params,
    )
    if df.empty:
        st.info("No data for the selected period.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    col1, col2 = st.columns(2)
    with col1:
        csv_download_button(df, "products_by_day.csv", "Export CSV")
    with col2:
        excel_download_button(df, "products_by_day.xlsx", "Export Excel")
