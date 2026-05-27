"""3-step first-run onboarding wizard."""

from __future__ import annotations

import streamlit as st

from tikitaka_dwh.ui.components import run_async


def render_onboarding() -> None:
    st.title("Welcome to Tiki-Taka PAY DWH")
    step = st.session_state.get("onboarding_step", 1)

    if step == 1:
        _step_welcome()
    elif step == 2:
        _step_credentials()
    elif step == 3:
        _step_backfill()


def _step_welcome() -> None:
    st.markdown(
        """
        ### Step 1 of 3 — Welcome

        This app downloads your Tikitaka point-of-sale data and stores it
        **locally on your computer**. No data is sent to any cloud service.

        You will need:
        - Your **username** (email) and **password** for the Tikitaka management portal.
        - A working internet connection for the initial sync.

        After the first sync, the app works fully offline.
        """
    )
    if st.button("Get started →", type="primary"):
        st.session_state["onboarding_step"] = 2
        st.rerun()


def _step_credentials() -> None:
    st.markdown("### Step 2 of 3 — Login credentials")
    st.info("Use the same username and password you log in to manage.tikitaka.lv with.")

    username = st.text_input("Username (email)", key="onb_username")
    password = st.text_input("Password", type="password", key="onb_password")

    col_test, col_next = st.columns([2, 1])

    with col_test:
        if st.button("Test connection", disabled=not (username and password)):
            with st.spinner("Connecting …"):
                ok, msg = _test_connection(username, password)
            if ok:
                st.success(f"Connection successful! {msg}")
                st.session_state["onb_tested"] = True
            else:
                st.error(f"Connection failed: {msg}")
                st.session_state["onb_tested"] = False

    with col_next:
        tested = st.session_state.get("onb_tested", False)
        if st.button("Save & continue →", type="primary", disabled=not tested):
            from tikitaka_dwh.auth import save_credentials

            save_credentials(username, password)
            st.session_state["onboarding_step"] = 3
            st.rerun()

    if st.button("← Back"):
        st.session_state["onboarding_step"] = 1
        st.rerun()


def _step_backfill() -> None:
    st.markdown("### Step 3 of 3 — Initial data sync")
    st.info(
        "The first sync downloads all your historical data. "
        "This may take a few minutes depending on your data volume."
    )

    if st.button("Start sync", type="primary", key="onb_start_sync"):
        _run_backfill()
        return

    if st.session_state.get("onb_sync_done"):
        st.success("Sync complete! Redirecting to dashboards …")
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
        st.error("Credentials not found — please go back to step 2.")
        return

    username, password = creds
    settings = get_settings()
    ensure_app_dirs()
    staging_dir = settings.app_data_dir / "lake" / "staging"

    bar = st.progress(0, text="Starting sync …")

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
                bar.progress(min(frac, 0.99), text=f"Downloaded {done} documents …")

            return await engine.run_backfill(progress=progress)

    try:
        count = run_async(_do())
        load_staging_to_warehouse(
            settings.app_data_dir / "warehouse.duckdb",
            staging_dir,
        )
        bar.progress(1.0, text=f"Done — {count} documents synced.")
        st.session_state["onb_sync_done"] = True
        st.rerun()
    except Exception as exc:
        bar.empty()
        st.error(f"Sync failed: {exc}")
