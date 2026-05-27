"""Shared Streamlit widgets: filters, exports, error cards."""

from __future__ import annotations

import asyncio
import io
import threading
from collections.abc import Coroutine
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import duckdb
import pandas as pd
import streamlit as st


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine from Streamlit's sync context.

    Streamlit >=1.18 executes scripts inside an async runner, so calling
    asyncio.run() directly raises RuntimeError.  Spawning a daemon thread
    with its own fresh event loop sidesteps the parent-loop conflict on every
    Streamlit version.

    The current script-run context is forwarded to the worker thread so that
    any Streamlit calls made inside the coroutine (e.g. progress bar updates)
    don't raise NoSessionContext.
    """
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

    ctx = get_script_run_ctx()
    result_holder: list[Any] = []
    exc_holder: list[BaseException] = []

    def _target() -> None:
        add_script_run_ctx(threading.current_thread(), ctx)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_holder.append(loop.run_until_complete(coro))
        except BaseException as exc:
            exc_holder.append(exc)
        finally:
            loop.close()

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join()

    if exc_holder:
        raise exc_holder[0]
    return result_holder[0] if result_holder else None


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


@st.cache_resource
def get_db_path() -> Path:
    from tikitaka_dwh.config import get_settings

    return get_settings().app_data_dir / "warehouse.duckdb"


def query(sql: str, params: list | None = None) -> pd.DataFrame:
    db = get_db_path()
    if not db.exists():
        return pd.DataFrame()
    con = duckdb.connect(str(db), read_only=True)
    try:
        if params:
            return con.execute(sql, params).df()
        return con.execute(sql).df()
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


def warehouse_exists() -> bool:
    db = get_db_path()
    if not db.exists():
        return False
    try:
        con = duckdb.connect(str(db), read_only=True)
        con.execute("SELECT 1 FROM fct_documents LIMIT 1")
        con.close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Sidebar global filters — stored in st.session_state
# ---------------------------------------------------------------------------


def render_sidebar_filters() -> dict:
    """Render date-range + store + POS filters. Returns dict of active values."""
    st.sidebar.header("Filters")

    default_end = date.today()
    default_start = default_end - timedelta(days=29)

    start = st.sidebar.date_input("From", value=default_start, key="filter_start")
    end = st.sidebar.date_input("To", value=default_end, key="filter_end")

    stores_df = query("SELECT DISTINCT store_number FROM fct_documents WHERE store_number IS NOT NULL ORDER BY 1")
    store_options = stores_df["store_number"].tolist() if not stores_df.empty else []
    selected_stores = st.sidebar.multiselect("Stores", store_options, default=store_options, key="filter_stores")

    pos_df = query("SELECT DISTINCT pos_id FROM fct_documents WHERE pos_id IS NOT NULL ORDER BY 1")
    pos_options = [str(p) for p in pos_df["pos_id"].tolist()] if not pos_df.empty else []
    selected_pos = st.sidebar.multiselect("POS terminals", pos_options, default=pos_options, key="filter_pos")

    return {
        "start": start,
        "end": end,
        "stores": selected_stores,
        "pos": [int(p) for p in selected_pos],
    }


def date_store_pos_where(filters: dict, alias: str = "") -> tuple[str, list]:
    """Return (WHERE snippet, params) for the standard filters."""
    pre = f"{alias}." if alias else ""
    clauses = [
        f"{pre}doc_date BETWEEN ? AND ?",
    ]
    params: list = [str(filters["start"]), str(filters["end"])]

    if filters["stores"]:
        placeholders = ", ".join("?" * len(filters["stores"]))
        clauses.append(f"{pre}store_number IN ({placeholders})")
        params.extend(filters["stores"])

    if filters["pos"]:
        placeholders = ", ".join("?" * len(filters["pos"]))
        clauses.append(f"{pre}pos_id IN ({placeholders})")
        params.extend(filters["pos"])

    return " AND ".join(clauses), params


# ---------------------------------------------------------------------------
# Sync status + button in sidebar
# ---------------------------------------------------------------------------


def render_sync_status() -> None:
    from tikitaka_dwh.config import get_settings
    from tikitaka_dwh.sync.watermark import WatermarkStore

    db_path = get_settings().app_data_dir / "warehouse.duckdb"
    if not db_path.exists():
        st.sidebar.caption("No data synced yet.")
        return

    try:
        wm = WatermarkStore(db_path)
        last = wm.get_last_sync_completed()
        if last:
            st.sidebar.caption(f"Last synced: {last.strftime('%Y-%m-%d %H:%M')} UTC")
        else:
            st.sidebar.caption("Never synced.")
    except Exception:
        pass


def render_sync_button() -> None:
    if st.sidebar.button("Sync now", use_container_width=True):
        _run_sync()


def _run_sync() -> None:
    import httpx

    from tikitaka_dwh.auth import TokenProvider, load_credentials
    from tikitaka_dwh.api.client import TikitakaClient
    from tikitaka_dwh.config import get_settings
    from tikitaka_dwh.sync.engine import SyncEngine
    from tikitaka_dwh.sync.watermark import WatermarkStore
    from tikitaka_dwh.warehouse.db import initialize_warehouse, load_staging_to_warehouse

    settings = get_settings()
    creds = load_credentials()
    if not creds:
        st.sidebar.error("No credentials stored. Please complete onboarding.")
        return

    username, password = creds
    staging_dir = settings.app_data_dir / "lake" / "staging"
    progress_bar = st.sidebar.progress(0, text="Connecting …")

    async def _do_sync() -> int:
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
                progress_bar.progress(min(frac, 0.99), text=f"Syncing … {done} docs")

            return await engine.run_incremental(progress=progress)

    try:
        count = run_async(_do_sync())
        load_staging_to_warehouse(
            settings.app_data_dir / "warehouse.duckdb",
            settings.app_data_dir / "lake" / "staging",
        )
        progress_bar.progress(1.0, text=f"Done — {count} new documents.")
        st.cache_data.clear()
        st.rerun()
    except Exception as exc:
        progress_bar.empty()
        msg = str(exc) or type(exc).__name__
        st.sidebar.error(f"Sync failed: {msg}")


# ---------------------------------------------------------------------------
# CSV / Excel export helpers
# ---------------------------------------------------------------------------


def csv_download_button(df: pd.DataFrame, filename: str, label: str = "Export CSV") -> None:
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(label=label, data=csv, file_name=filename, mime="text/csv")


def excel_download_button(df: pd.DataFrame, filename: str, label: str = "Export Excel") -> None:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    st.download_button(
        label=label,
        data=buf.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Error card
# ---------------------------------------------------------------------------


def error_card(title: str, exc: Exception) -> None:
    import traceback

    diag = traceback.format_exc()
    st.error(f"**{title}**\n\n{exc}")
    with st.expander("Copy diagnostics"):
        st.code(diag)
