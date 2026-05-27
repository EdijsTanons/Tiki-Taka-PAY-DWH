"""Page 6 — Z Reports: end-of-day summary."""

from __future__ import annotations

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


def render() -> None:
    st.title("Z Reports — End of Day Summary")
    filters = st.session_state.get("filters", {})
    if not filters:
        st.warning("Apply filters in the sidebar.")
        return
    try:
        _render_page(filters)
    except Exception as exc:
        error_card("Z Reports page error", exc)


def _render_page(filters: dict) -> None:
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
        st.info("No Z reports found for the selected period.")
        return

    # Parse ceka_saturs XML for each row
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
    c1.metric("Z Reports",          len(df))
    c2.metric("Total Sales",        f"€{total_revenue:,.2f}")
    c3.metric("Avg Daily Revenue",  f"€{avg_daily:,.2f}")
    c4.metric("Voided Transactions", cancelled_ttl)

    st.divider()

    # ── Daily revenue chart ────────────────────────────────────────────────────
    daily = (
        df.groupby("doc_date", as_index=False)["sales_total"]
        .sum()
        .rename(columns={"sales_total": "gross"})
    )
    daily["doc_date"] = daily["doc_date"].astype(str)

    chart = (
        alt.Chart(daily)
        .mark_bar(color="#4C8BF5")
        .encode(
            x=alt.X("doc_date:O", title="Date", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("gross:Q", title="Sales (€)"),
            tooltip=[
                alt.Tooltip("doc_date:O", title="Date"),
                alt.Tooltip("gross:Q",    title="Sales (€)", format=",.2f"),
            ],
        )
        .properties(height=240)
    )
    st.subheader("Daily revenue from Z reports")
    st.altair_chart(chart, use_container_width=True)

    st.divider()

    # ── Z Report register table ────────────────────────────────────────────────
    st.subheader("Z Report register")

    with st.expander("About the Match column"):
        st.markdown(
            """
**Match** compares two numbers for each Z report:

- **Calculated (€)** — sum of all sale transactions for that day + store + POS from the database
- **Z-stated (€)** — the "KOPĀ" (total) value parsed directly from the Z report receipt

| Symbol | Meaning |
|--------|---------|
| ✓ | Z-stated total matches calculated sales within €0.01 |
| ✗ | They differ |
| ? | Z report XML could not be parsed |

**Note:** when a POS has several Z reports on the same day (intermediate reports), \
the Calculated column shows the *full day's* sales — so all but the last Z report of the day \
will show ✗. That is expected. Only the final Z report of the day should show ✓.
            """
        )

    display = df[[
        "doc_date", "store_number", "pos_id", "z_num",
        "operator_id", "operator_name",
        "sale_count", "sales_total", "z_total",
        "match",
        "cancelled_count", "cancelled_amount",
        "refund_count", "cash_in", "cash_out",
    ]].copy()
    display.columns = [
        "Date", "Store", "POS", "Z#",
        "Operator ID", "Operator",
        "Txns", "Calculated (€)", "Z-stated (€)",
        "Match",
        "Voided #", "Voided (€)",
        "Refunds #", "Cash in (€)", "Cash out (€)",
    ]

    def _style_match(val: str) -> str:
        if val == "✗":
            return "background-color: #ffcccc"
        if val == "✓":
            return "background-color: #ccffcc"
        return ""

    st.dataframe(
        display.style.map(_style_match, subset=["Match"]),
        use_container_width=True,
        hide_index=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        csv_download_button(display, "z_reports.csv", "Export CSV")
    with col2:
        excel_download_button(display, "z_reports.xlsx", "Export Excel")

    st.divider()

    # ── VAT summary ────────────────────────────────────────────────────────────
    vat_rows: list[dict] = []
    for _, row in df.iterrows():
        for vr in row["vat_rows"]:
            vat_rows.append({
                "Code":        vr["code"],
                "Rate %":      vr["rate"],
                "Taxable (€)": vr["taxable"],
                "VAT (€)":     vr["vat"],
            })

    if vat_rows:
        vat_df = pd.DataFrame(vat_rows)
        vat_summary = (
            vat_df.groupby(["Code", "Rate %"], as_index=False)
            .agg({"Taxable (€)": "sum", "VAT (€)": "sum"})
            .sort_values("Code")
        )
        st.subheader("VAT breakdown (period total from Z reports)")
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
        st.subheader(f"Days with sales but no Z report — {len(gaps_df)} found")
        gaps_df.columns = ["Date", "Store", "POS", "Txns", "Sales (€)"]
        st.dataframe(gaps_df, use_container_width=True, hide_index=True)
    else:
        st.success("All sales days have a corresponding Z report.")
