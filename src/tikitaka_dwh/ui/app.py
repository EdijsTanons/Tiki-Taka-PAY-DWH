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
    from tikitaka_dwh.ui.i18n import render_language_selector, t

    ensure_app_dirs()
    configure_logging()
    init_sentry()

    render_language_selector()

    if not _has_credentials():
        from tikitaka_dwh.ui.onboarding import render_onboarding

        render_onboarding()
        return

    from tikitaka_dwh.ui.components import (
        render_sidebar_filters,
        render_sync_button,
        render_sync_status,
    )

    st.sidebar.title(t("sidebar_title"))
    render_sync_status()
    render_sync_button()
    st.sidebar.divider()
    filters = render_sidebar_filters()
    st.session_state["filters"] = filters

    pages = {
        t("nav_revenue"):    "01_revenue",
        t("nav_products"):   "02_products",
        t("nav_stores_pos"): "03_stores_pos",
        t("nav_heatmap"):    "04_heatmap",
        t("nav_vat"):        "05_vat",
        t("nav_z_reports"):  "06_z_reports",
        t("nav_settings"):   "settings",
        t("nav_diagnostics"):"diagnostics",
    }

    st.sidebar.divider()
    page = st.sidebar.radio(t("sidebar_navigate"), list(pages.keys()), label_visibility="collapsed")
    st.session_state["current_page"] = page

    if not _warehouse_has_data():
        st.info(t("no_data_hint"))
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
        from tikitaka_dwh.ui.i18n import t

        error_card(t("page_load_error", page=module_name), exc)


if __name__ == "__main__":
    main()
