"""Settings page — credentials, data folder, sync interval, Sentry opt-in."""

from __future__ import annotations

import shutil
from pathlib import Path

import streamlit as st


def render() -> None:
    st.title("Settings")
    try:
        _section_credentials()
        st.divider()
        _section_data_folder()
        st.divider()
        _section_sentry()
    except Exception as exc:
        from tikitaka_dwh.ui.components import error_card

        error_card("Settings page error", exc)


def _section_credentials() -> None:
    from tikitaka_dwh.auth import load_credentials, save_credentials, clear_credentials

    st.subheader("API credentials")
    creds = load_credentials()

    if creds:
        username, _ = creds
        st.success(f"Credentials stored (username: `{username}`).")
        if st.button("Change credentials"):
            st.session_state["settings_change_creds"] = True

    if not creds or st.session_state.get("settings_change_creds"):
        new_username = st.text_input("Username (email)", key="settings_new_id")
        new_password = st.text_input("Password", type="password", key="settings_new_secret")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Save credentials", type="primary", disabled=not (new_username and new_password)):
                save_credentials(new_username, new_password)
                st.session_state.pop("settings_change_creds", None)
                st.success("Credentials updated.")
                st.rerun()
        with c2:
            if st.button("Clear credentials", type="secondary"):
                clear_credentials()
                st.warning("Credentials cleared. You will be redirected to onboarding.")
                st.rerun()


def _section_data_folder() -> None:
    from tikitaka_dwh.config import get_settings

    settings = get_settings()
    st.subheader("Data folder")
    st.code(str(settings.app_data_dir))

    st.info(
        "To move your data folder, set the `TIKITAKA_APP_DATA_DIR` environment variable "
        "to the new path and restart the app. The existing warehouse will need to be "
        "manually copied to the new location."
    )

    db_path = settings.app_data_dir / "warehouse.duckdb"
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        st.caption(f"Warehouse size: {size_mb:.1f} MB")


def _section_sentry() -> None:
    import os

    st.subheader("Crash reporting (Sentry)")

    current_dsn = os.environ.get("TIKITAKA_SENTRY_DSN", "")
    enabled = bool(current_dsn)

    st.markdown(
        "Crash reports are **opt-in only**. When enabled, anonymised error traces are sent "
        "to Sentry. No customer data, credentials, or sales figures are included."
    )

    if enabled:
        st.success("Crash reporting is enabled.")
        if st.button("Disable crash reporting"):
            st.info(
                "To disable, unset the `TIKITAKA_SENTRY_DSN` environment variable and restart the app."
            )
    else:
        st.warning("Crash reporting is disabled.")
        dsn_input = st.text_input("Enter Sentry DSN to enable (optional)", key="settings_dsn")
        if st.button("Enable crash reporting", disabled=not dsn_input):
            st.info(
                f"Set `TIKITAKA_SENTRY_DSN={dsn_input}` as an environment variable and restart the app."
            )
