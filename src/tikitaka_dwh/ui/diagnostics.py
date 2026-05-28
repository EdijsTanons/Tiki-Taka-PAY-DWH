"""Diagnostics panel — app version, paths, DB size, last sync, API reachability."""

from __future__ import annotations

import platform
from pathlib import Path

import streamlit as st

from tikitaka_dwh.ui.components import run_async
from tikitaka_dwh.ui.i18n import t


def render() -> None:
    st.title(t("diag_title"))
    try:
        _render_diagnostics()
    except Exception as exc:
        from tikitaka_dwh.ui.components import error_card

        error_card(t("diag_error"), exc)

    st.divider()
    try:
        _render_raw_section()
    except Exception as exc:
        from tikitaka_dwh.ui.components import error_card

        error_card(t("diag_raw_error"), exc)


def _render_diagnostics() -> None:
    import tikitaka_dwh
    from tikitaka_dwh.config import get_settings

    settings = get_settings()
    db_path = settings.app_data_dir / "warehouse.duckdb"

    lines: list[str] = []
    lines.append(f"App version:    {tikitaka_dwh.__version__}")
    lines.append(f"Python:         {platform.python_version()}")
    lines.append(f"Platform:       {platform.platform()}")
    lines.append(f"Data dir:       {settings.app_data_dir}")

    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        lines.append(f"DB size:        {size_mb:.2f} MB")
    else:
        lines.append("DB size:        (not initialized)")

    try:
        from tikitaka_dwh.sync.watermark import WatermarkStore

        wm = WatermarkStore(db_path)
        last = wm.get_last_sync_completed()
        last_id = wm.get_last_seen_id()
        lines.append(f"Last sync:      {last.strftime('%Y-%m-%d %H:%M:%S UTC') if last else 'never'}")
        lines.append(f"Last seen ID:   {last_id if last_id else 'none'}")
    except Exception as e:
        lines.append(f"Sync state:     error ({e})")

    lines.append("")
    lines.append("─── API reachability ───")
    reachable, api_msg = _check_api(settings.api_base_url)
    lines.append(f"API endpoint:   {settings.api_base_url}")
    lines.append(f"Status:         {'✓ reachable' if reachable else '✗ unreachable'}")
    lines.append(f"Detail:         {api_msg}")

    lines.append("")
    lines.append("─── Recent log entries ───")
    log_tail = _read_log_tail(settings.app_data_dir / "logs" / "app.log", n=20)
    lines.extend(log_tail)

    diag_text = "\n".join(lines)

    st.subheader(t("diag_system_info"))
    st.code(diag_text, language="text")

    st.download_button(
        t("diag_copy_download"),
        data=diag_text,
        file_name="tikitaka_diag.txt",
        mime="text/plain",
    )


def _check_api(base_url: str) -> tuple[bool, str]:
    import httpx

    async def _do() -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                resp = await http.get(f"{base_url}/docs", follow_redirects=True)
                return True, f"HTTP {resp.status_code}"
        except httpx.ConnectError as e:
            return False, f"Connection refused: {e}"
        except httpx.TimeoutException:
            return False, "Timeout after 5 s"
        except Exception as e:
            return False, str(e)

    try:
        return run_async(_do())
    except Exception as e:
        return False, str(e)


def _render_raw_section() -> None:
    """Show raw JSON stats and offer a 'Rebuild from raw' action."""
    from tikitaka_dwh.config import get_settings
    from tikitaka_dwh.warehouse.db import audit_raw, rebuild_from_raw, initialize_warehouse

    settings = get_settings()
    raw_dir = settings.app_data_dir / "lake" / "raw"
    db_path = settings.app_data_dir / "warehouse.duckdb"

    st.subheader(t("diag_raw_title"))

    if not raw_dir.exists() or not any(raw_dir.rglob("*.json")):
        st.info(t("diag_no_raw"))
        return

    with st.spinner(t("diag_scanning")):
        stats = audit_raw(raw_dir)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("diag_json_files"), f"{stats['files']:,}")
    col2.metric(t("diag_total_records"), f"{stats['total_docs']:,}")
    col3.metric(t("diag_unique_ids"), f"{stats['unique_ids']:,}")
    dup_label = f"{stats['duplicate_docs']:,}"
    col4.metric(
        t("diag_duplicates"),
        dup_label,
        delta=None if stats["duplicate_docs"] == 0 else f"−{dup_label}",
        delta_color="inverse",
    )

    if stats["min_id"] is not None:
        st.caption(t("diag_doc_id_range", min=f"{stats['min_id']:,}", max=f"{stats['max_id']:,}"))

    st.markdown(t("diag_rebuild_info"))

    set_wm = st.checkbox(t("diag_update_watermark"), value=False)

    if st.button(t("diag_rebuild_btn"), type="primary"):
        watermark = None
        if set_wm:
            from tikitaka_dwh.sync.watermark import WatermarkStore
            watermark = WatermarkStore(db_path)

        if not db_path.exists():
            initialize_warehouse(db_path)

        with st.spinner(t("diag_loading_docs", n=stats["unique_ids"])):
            result = rebuild_from_raw(
                db_path=db_path,
                raw_dir=raw_dir,
                watermark=watermark,
                set_watermark=set_wm,
            )

        done_msg = t("diag_rebuild_done", rows=result["warehouse_rows"])
        if set_wm:
            done_msg += t("diag_watermark_set", mid=result["max_id"])
        st.success(done_msg)
        st.cache_data.clear()
        st.rerun()


def _read_log_tail(log_path: Path, n: int = 20) -> list[str]:
    if not log_path.exists():
        return ["(no log file found)"]
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:] if len(lines) >= n else lines
    except Exception as e:
        return [f"(could not read log: {e})"]
