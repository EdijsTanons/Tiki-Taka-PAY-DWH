"""3-step first-run onboarding wizard."""

from __future__ import annotations

import streamlit as st

from tikitaka_dwh.ui.components import run_async
from tikitaka_dwh.ui.i18n import t


def render_onboarding() -> None:
    st.title(t("onb_title"))
    step = st.session_state.get("onboarding_step", 1)

    if step == 1:
        _step_welcome()
    elif step == 2:
        _step_credentials()
    elif step == 3:
        _step_backfill()


def _step_welcome() -> None:
    st.markdown(t("onb_step1_heading"))
    st.markdown(t("onb_step1_body"))
    if st.button(t("onb_get_started"), type="primary"):
        st.session_state["onboarding_step"] = 2
        st.rerun()


def _step_credentials() -> None:
    st.markdown(t("onb_step2_heading"))
    st.info(t("onb_step2_info"))

    username = st.text_input(t("onb_username"), key="onb_username")
    password = st.text_input(t("onb_password"), type="password", key="onb_password")

    col_test, col_next = st.columns([2, 1])

    with col_test:
        if st.button(t("onb_test_connection"), disabled=not (username and password)):
            with st.spinner(t("onb_connecting")):
                ok, msg = _test_connection(username, password)
            if ok:
                st.success(t("onb_conn_ok", msg=msg))
                st.session_state["onb_tested"] = True
            else:
                st.error(t("onb_conn_fail", msg=msg))
                st.session_state["onb_tested"] = False

    with col_next:
        tested = st.session_state.get("onb_tested", False)
        if st.button(t("onb_save_continue"), type="primary", disabled=not tested):
            from tikitaka_dwh.auth import save_credentials

            save_credentials(username, password)
            st.session_state["onboarding_step"] = 3
            st.rerun()

    if st.button(t("onb_back")):
        st.session_state["onboarding_step"] = 1
        st.rerun()


def _step_backfill() -> None:
    st.markdown(t("onb_step3_heading"))
    st.info(t("onb_step3_info"))

    if st.button(t("onb_start_sync"), type="primary", key="onb_start_sync"):
        _run_backfill()
        return

    if st.session_state.get("onb_sync_done"):
        st.success(t("onb_sync_complete"))
        st.session_state.pop("onboarding_step", None)
        st.session_state.pop("onb_sync_done", None)
        st.session_state.pop("onb_tested", None)
        st.rerun()


def _test_connection(username: str, password: str) -> tuple[bool, str]:
    import httpx

    from tikitaka_dwh.auth import TokenProvider
    from tikitaka_dwh.config import get_settings

    settings = get_settings()

    async def _do() -> tuple[bool, str]:
        async with httpx.AsyncClient() as http:
            provider = TokenProvider(
                lambda: username,
                lambda: password,
                base_url=settings.api_base_url,
                http_client=http,
            )
            try:
                token = await provider.get_token()
                return True, f"Token acquired (length {len(token)})."
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    return False, "Invalid credentials (401). Check your client ID and secret."
                return False, f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            except Exception as exc:
                return False, str(exc)

    try:
        return run_async(_do())
    except Exception as exc:
        return False, str(exc)


def _run_backfill() -> None:
    import httpx

    from tikitaka_dwh.auth import TokenProvider, load_credentials
    from tikitaka_dwh.api.client import TikitakaClient
    from tikitaka_dwh.config import get_settings, ensure_app_dirs
    from tikitaka_dwh.sync.engine import SyncEngine
    from tikitaka_dwh.sync.watermark import WatermarkStore
    from tikitaka_dwh.warehouse.db import initialize_warehouse, load_staging_to_warehouse

    creds = load_credentials()
    if not creds:
        st.error(t("onb_no_creds"))
        return

    username, password = creds
    settings = get_settings()
    ensure_app_dirs()
    staging_dir = settings.app_data_dir / "lake" / "staging"

    bar = st.progress(0, text=t("onb_sync_starting"))

    async def _do() -> int:
        async with httpx.AsyncClient() as http:
            provider = TokenProvider(
                lambda: username,
                lambda: password,
                base_url=settings.api_base_url,
                http_client=http,
            )
            client = TikitakaClient(settings.api_base_url, provider, http)
            watermark = WatermarkStore(settings.app_data_dir / "warehouse.duckdb")
            initialize_warehouse(settings.app_data_dir / "warehouse.duckdb")
            engine = SyncEngine(
                client=client,
                raw_dir=settings.app_data_dir / "lake" / "raw",
                watermark=watermark,
                staging_dir=staging_dir,
            )

            def progress(done: int, total: int | None) -> None:
                frac = (done / total) if total else 0.0
                bar.progress(min(frac, 0.99), text=t("onb_sync_progress", n=done))

            return await engine.run_backfill(progress=progress)

    try:
        count = run_async(_do())
        load_staging_to_warehouse(
            settings.app_data_dir / "warehouse.duckdb",
            staging_dir,
        )
        bar.progress(1.0, text=t("onb_sync_done_bar", n=count))
        st.session_state["onb_sync_done"] = True
        st.rerun()
    except Exception as exc:
        bar.empty()
        st.error(t("onb_sync_failed", exc=exc))
