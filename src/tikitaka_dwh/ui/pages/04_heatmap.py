"""Page 4 — Heatmap: hour-of-day × day-of-week."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from tikitaka_dwh.ui.components import (
    date_store_pos_where,
    error_card,
    query,
)

_DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_HOURS = list(range(24))


def render() -> None:
    st.title("Heatmap — Peak times")
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning("Apply filters in the sidebar.")
        return

    try:
        metric = st.radio("Show", ["Transactions", "Revenue (€)"], horizontal=True, key="hm_metric")
        _render_heatmap(filters, metric)
        st.divider()
        _render_hourly_bar(filters)
    except Exception as exc:
        error_card("Heatmap page error", exc)


def _render_heatmap(filters: dict, metric: str) -> None:
    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT
            HOUR(doc_datetime_local)    AS hour_of_day,
            DAYOFWEEK(doc_date)         AS dow,
            COUNT(*)                    AS txn_count,
            SUM(doc_sum)                AS gross
        FROM fct_documents
        WHERE doc_type = 'sale' AND {where}
        GROUP BY hour_of_day, dow
        ORDER BY dow, hour_of_day
        """,
        params,
    )
    if df.empty:
        st.info("No data for the selected period.")
        return

    val_col = "txn_count" if metric == "Transactions" else "gross"
    fmt = ".0f" if metric == "Transactions" else ",.2f"

    # Map DuckDB DAYOFWEEK (1=Mon…7=Sun in DuckDB) to day labels
    dow_map = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
    df["day"] = df["dow"].map(dow_map).fillna("?")
    df["hour_label"] = df["hour_of_day"].apply(lambda h: f"{int(h):02d}:00")

    chart = (
        alt.Chart(df)
        .mark_rect()
        .encode(
            x=alt.X("hour_label:O", title="Hour", sort=[f"{h:02d}:00" for h in _HOURS]),
            y=alt.Y("day:O", title=None, sort=_DOW_LABELS),
            color=alt.Color(
                f"{val_col}:Q",
                scale=alt.Scale(scheme="yelloworangered"),
                title=metric,
            ),
            tooltip=[
                alt.Tooltip("day:O", title="Day"),
                alt.Tooltip("hour_label:O", title="Hour"),
                alt.Tooltip(f"{val_col}:Q", title=metric, format=fmt),
            ],
        )
        .properties(height=220)
    )

    st.subheader(f"{metric} by hour of day & day of week")
    st.altair_chart(chart, use_container_width=True)


def _render_hourly_bar(filters: dict) -> None:
    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT
            HOUR(doc_datetime_local)    AS hour_of_day,
            COUNT(*)                    AS txn_count,
            SUM(doc_sum)                AS gross
        FROM fct_documents
        WHERE doc_type = 'sale' AND {where}
        GROUP BY hour_of_day
        ORDER BY hour_of_day
        """,
        params,
    )
    if df.empty:
        return
    df["hour_label"] = df["hour_of_day"].apply(lambda h: f"{int(h):02d}:00")
    st.subheader("Transactions by hour (all days)")
    st.bar_chart(df.set_index("hour_label")["txn_count"])
