"""Page 4 — Heatmap: hour-of-day × day-of-week."""

from __future__ import annotations

from typing import Any

import altair as alt
import streamlit as st

from tikitaka_dwh.ui.components import (
    date_store_pos_where,
    error_card,
    query,
)
from tikitaka_dwh.ui.i18n import t

_HOURS = list(range(24))


def render() -> None:
    st.title(t("hm_title"))
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning(t("apply_filters"))
        return

    try:
        metric = st.radio(
            t("hm_show"),
            [t("hm_transactions"), t("hm_revenue")],
            horizontal=True,
            key="hm_metric",
        )
        _render_heatmap(filters, metric)
        st.divider()
        _render_hourly_bar(filters)
    except Exception as exc:
        error_card(t("hm_page_error"), exc)


def _render_heatmap(filters: dict[str, Any], metric: str) -> None:
    dow_labels = [t("hm_mon"), t("hm_tue"), t("hm_wed"), t("hm_thu"), t("hm_fri"), t("hm_sat"), t("hm_sun")]
    # Keys follow ISODOW semantics: Monday=1 … Sunday=7 (DAYOFWEEK would give Sunday=0)
    dow_map = {1: t("hm_mon"), 2: t("hm_tue"), 3: t("hm_wed"), 4: t("hm_thu"), 5: t("hm_fri"), 6: t("hm_sat"), 7: t("hm_sun")}

    where, params = date_store_pos_where(filters)
    df = query(
        f"""
        SELECT
            HOUR(doc_datetime_local)    AS hour_of_day,
            ISODOW(doc_date)            AS dow,
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
        st.info(t("hm_no_data"))
        return

    transactions_label = t("hm_transactions")
    val_col = "txn_count" if metric == transactions_label else "gross"
    fmt = ".0f" if metric == transactions_label else ",.2f"

    df["day"] = df["dow"].map(dow_map).fillna("?")
    df["hour_label"] = df["hour_of_day"].apply(lambda h: f"{int(h):02d}:00")

    chart = (
        alt.Chart(df)
        .mark_rect()
        .encode(
            x=alt.X("hour_label:O", title=t("hm_hour_axis"), sort=[f"{h:02d}:00" for h in _HOURS]),
            y=alt.Y("day:O", title=None, sort=dow_labels),
            color=alt.Color(
                f"{val_col}:Q",
                scale=alt.Scale(scheme="yelloworangered"),
                title=metric,
            ),
            tooltip=[
                alt.Tooltip("day:O", title=t("hm_day_axis")),
                alt.Tooltip("hour_label:O", title=t("hm_hour_axis")),
                alt.Tooltip(f"{val_col}:Q", title=metric, format=fmt),
            ],
        )
        .properties(height=220)
    )

    st.subheader(t("hm_subheader", metric=metric))
    st.altair_chart(chart, use_container_width=True)


def _render_hourly_bar(filters: dict[str, Any]) -> None:
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
    st.subheader(t("hm_hourly_bar"))
    st.bar_chart(df.set_index("hour_label")["txn_count"])
