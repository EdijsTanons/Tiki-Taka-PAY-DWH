"""Settings page — credentials, data folder, sync interval, Sentry opt-in."""

from __future__ import annotations

import shutil
from pathlib import Path

import streamlit as st

from tikitaka_dwh.ui.i18n import t


def render() -> None:
    st.title(t("settings_title"))
    try:
        _section_credentials()
        st.divider()
        _section_data_folder()
        st.divider()
        _section_sentry()
    except Exception as exc:
        from tikitaka_dwh.ui.components import error_card

        error_card(t("settings_page_error"), exc)


def _section_credentials() -> None:
    from tikitaka_dwh.auth import load_credentials, save_credentials, clear_credentials

    st.subheader(t("settings_api_creds"))
    creds = load_credentials()

    if creds:
        username, _ = creds
        st.success(t("settings_creds_stored", u=username))
        if st.button(t("settings_change_creds")):
            st.session_state["settings_change_creds"] = True

    if not creds or st.session_state.get("settings_change_creds"):
        new_username = st.text_input(t("settings_username"), key="settings_new_id")
        new_password = st.text_input(t("settings_password"), type="password", key="settings_new_secret")
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("settings_save_creds"), type="primary", disabled=not (new_username and new_password)):
                save_credentials(new_username, new_password)
                st.session_state.pop("settings_change_creds", None)
                st.success(t("settings_creds_updated"))
                st.rerun()
        with c2:
            if st.button(t("settings_clear_creds"), type="secondary"):
                clear_credentials()
                st.warning(t("settings_creds_cleared"))
                st.rerun()


def _section_data_folder() -> None:
    from tikitaka_dwh.config import get_settings

    settings = get_settings()
    st.subheader(t("settings_data_folder"))
    st.code(str(settings.app_data_dir))
    st.info(t("settings_data_folder_info"))

    db_path = settings.app_data_dir / "warehouse.duckdb"
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        st.caption(t("settings_warehouse_size", n=f"{size_mb:.1f}"))


def _section_sentry() -> None:
    import os

    st.subheader(t("settings_sentry"))

    current_dsn = os.environ.get("TIKITAKA_SENTRY_DSN", "")
    enabled = bool(current_dsn)

    st.markdown(t("settings_sentry_info"))

    if enabled:
        st.success(t("settings_sentry_enabled"))
        if st.button(t("settings_sentry_disable")):
            st.info(t("settings_sentry_disable_info"))
    else:
        st.warning(t("settings_sentry_disabled"))
        dsn_input = st.text_input(t("settings_sentry_dsn_input"), key="settings_dsn")
        if st.button(t("settings_sentry_enable"), disabled=not dsn_input):
            st.info(t("settings_sentry_enable_info", dsn=dsn_input))
