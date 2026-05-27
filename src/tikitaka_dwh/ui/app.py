"""Streamlit app entrypoint — page config, sidebar, routing."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Tiki-Taka PAY DWH",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _has_credentials() -> bool:
    from tikitaka_dwh.auth import load_credentials

    return load_credentials() is not None


def _warehouse_has_data() -> bool:
    from tikitaka_dwh.ui.components import warehouse_exists

    return warehouse_exists()


def main() -> None:
    from tikitaka_dwh.config import ensure_app_dirs
    from tikitaka_dwh.observability.logging import configure_logging
    from tikitaka_dwh.observability.sentry import init_sentry

    ensure_app_dirs()
    configure_logging()
    init_sentry()

    if not _has_credentials():
        from tikitaka_dwh.ui.onboarding import render_onboarding

        render_onboarding()
        return

    from tikitaka_dwh.ui.components import (
        render_sidebar_filters,
        render_sync_status,
        render_sync_button,
    )

    st.sidebar.title("Tiki-Taka PAY DWH")
    render_sync_status()
    render_sync_button()
    st.sidebar.divider()
    filters = render_sidebar_filters()
    st.session_state["filters"] = filters

    pages = {
        "Revenue": "01_revenue",
        "Products": "02_products",
        "Stores & POS": "03_stores_pos",
        "Heatmap": "04_heatmap",
        "VAT": "05_vat",
        "Z Reports": "06_z_reports",
        "Settings": "settings",
        "Diagnostics": "diagnostics",
    }

    st.sidebar.divider()
    page = st.sidebar.radio("Navigate", list(pages.keys()), label_visibility="collapsed")
    st.session_state["current_page"] = page

    if not _warehouse_has_data():
        st.info("No data yet. Click **Sync now** in the sidebar to load your first batch.")
        return

    _load_page(pages[page])


def _load_page(module_name: str) -> None:
    import importlib

    try:
        if module_name in ("settings", "diagnostics"):
            mod = importlib.import_module(f"tikitaka_dwh.ui.{module_name}")
        else:
            mod = importlib.import_module(f"tikitaka_dwh.ui.pages.{module_name}")
        mod.render()
    except Exception as exc:
        from tikitaka_dwh.ui.components import error_card

        error_card(f"Page '{module_name}' failed to load", exc)


if __name__ == "__main__":
    main()
