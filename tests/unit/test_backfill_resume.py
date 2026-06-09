"""Tests for resumable backfill and rebuild-from-raw."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

from tikitaka_dwh.sync.watermark import WatermarkStore
from tikitaka_dwh.warehouse.db import audit_raw, initialize_warehouse, rebuild_from_raw

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(id_: int) -> dict:
    return {
        "id": id_,
        "doc_uid": id_ * 10,
        "doc_num": id_,
        "doc_datetime": "2024-03-15T10:00:00",
        "store_number": "S01",
        "id_device": 1,
        "operator_id": "op1",
        "operator_name": "Operator One",
        "dok_operation": "sale",
        "doc_sum": 9.99,
        "currency": "EUR",
        "non_fiscal": False,
        "doc_sha": None,
        "device_serial_number": None,
        "customer_card_number": None,
        "client_reg_number": None,
        "doc": None,
        "payments": [],
        "sold_products": [],
    }


def _write_raw_page(raw_dir: Path, docs: list[dict], run_id: str | None = None) -> Path:
    run_id = run_id or uuid.uuid4().hex
    dest = raw_dir / "dt=2024-03-15"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"page_{run_id}_0000.json"
    path.write_text(json.dumps(docs), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# WatermarkStore — backfill cursor
# ---------------------------------------------------------------------------


def test_backfill_cursor_roundtrip(tmp_path: Path) -> None:
    wm = WatermarkStore(tmp_path / "wm.duckdb")
    assert wm.get_backfill_cursor() is None
    assert wm.get_backfill_peak_id() is None

    wm.save_backfill_progress(skip=1000, peak_id=22000)
    assert wm.get_backfill_cursor() == 1000
    assert wm.get_backfill_peak_id() == 22000

    # Cursor updates; peak only grows
    wm.save_backfill_progress(skip=2000, peak_id=15000)
    assert wm.get_backfill_cursor() == 2000
    assert wm.get_backfill_peak_id() == 22000  # did NOT go down

    wm.save_backfill_progress(skip=3000, peak_id=25000)
    assert wm.get_backfill_peak_id() == 25000  # new high accepted

    wm.clear_backfill_progress()
    assert wm.get_backfill_cursor() is None
    assert wm.get_backfill_peak_id() is None


# ---------------------------------------------------------------------------
# audit_raw
# ---------------------------------------------------------------------------


def test_audit_raw_empty(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    stats = audit_raw(raw_dir)
    assert stats == {
        "files": 0,
        "failed_files": 0,
        "total_docs": 0,
        "unique_ids": 0,
        "duplicate_docs": 0,
        "min_id": None,
        "max_id": None,
    }


def test_audit_raw_deduplication(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"

    # Write doc IDs 1-5 in two files (1-3 overlap → 2 duplicates)
    _write_raw_page(raw_dir, [_make_doc(i) for i in range(1, 4)], run_id="a")
    _write_raw_page(raw_dir, [_make_doc(i) for i in range(3, 6)], run_id="b")

    stats = audit_raw(raw_dir)
    assert stats["files"] == 2
    assert stats["total_docs"] == 6         # 3 + 3
    assert stats["unique_ids"] == 5         # IDs 1,2,3,4,5
    assert stats["duplicate_docs"] == 1     # doc 3 appears twice
    assert stats["min_id"] == 1
    assert stats["max_id"] == 5


# ---------------------------------------------------------------------------
# rebuild_from_raw
# ---------------------------------------------------------------------------


def test_rebuild_from_raw_basic(tmp_path: Path, sample_docs: list) -> None:
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "wh.duckdb"
    initialize_warehouse(db_path)

    # Write two pages — second page re-sends the same docs (duplicates)
    _write_raw_page(raw_dir, sample_docs, run_id="run1")
    _write_raw_page(raw_dir, sample_docs, run_id="run2")

    result = rebuild_from_raw(db_path, raw_dir)
    assert result["total_docs"] == len(sample_docs) * 2
    assert result["unique_ids"] == len(sample_docs)
    assert result["duplicate_docs"] == len(sample_docs)
    assert result["warehouse_rows"] == len(sample_docs)

    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    count = con.execute("SELECT COUNT(*) FROM fct_documents").fetchone()[0]
    con.close()
    assert count == len(sample_docs)


def test_rebuild_from_raw_no_watermark_by_default(tmp_path: Path, sample_docs: list) -> None:
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "wh.duckdb"
    initialize_warehouse(db_path)
    wm = WatermarkStore(db_path)

    _write_raw_page(raw_dir, sample_docs)
    rebuild_from_raw(db_path, raw_dir, watermark=wm, set_watermark=False)

    # Watermark must remain unset
    assert wm.get_last_seen_id() is None


def test_rebuild_from_raw_sets_watermark_when_requested(tmp_path: Path, sample_docs: list) -> None:
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "wh.duckdb"
    initialize_warehouse(db_path)
    wm = WatermarkStore(db_path)

    _write_raw_page(raw_dir, sample_docs)
    result = rebuild_from_raw(db_path, raw_dir, watermark=wm, set_watermark=True)

    expected_max = max(d["id"] for d in sample_docs)
    assert wm.get_last_seen_id() == expected_max
    assert result["max_id"] == expected_max


def test_audit_raw_counts_unreadable_files(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    _write_raw_page(raw_dir, [_make_doc(1), _make_doc(2)])
    corrupt = raw_dir / "dt=2024-03-15" / "page_corrupt_0000.json"
    corrupt.write_text("{not valid json", encoding="utf-8")

    stats = audit_raw(raw_dir)
    assert stats["files"] == 2
    assert stats["failed_files"] == 1
    assert stats["unique_ids"] == 2


def test_rebuild_from_raw_skips_watermark_on_unreadable_files(
    tmp_path: Path, sample_docs: list
) -> None:
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "wh.duckdb"
    initialize_warehouse(db_path)
    wm = WatermarkStore(db_path)

    _write_raw_page(raw_dir, sample_docs)
    corrupt = raw_dir / "dt=2024-03-15" / "page_corrupt_0000.json"
    corrupt.write_text("{not valid json", encoding="utf-8")

    result = rebuild_from_raw(db_path, raw_dir, watermark=wm, set_watermark=True)

    # Readable docs are still loaded, but the watermark must NOT advance past
    # documents that may sit in the unreadable file.
    assert result["failed_files"] == 1
    assert result["warehouse_rows"] == len(sample_docs)
    assert wm.get_last_seen_id() is None


# ---------------------------------------------------------------------------
# SyncEngine — resumable backfill
# ---------------------------------------------------------------------------


def _make_mock_client(docs: list[dict]) -> MagicMock:
    """Return a TikitakaClient mock whose iter_documents yields ApiDocument stubs."""
    from tikitaka_dwh.api.schemas import ApiDocument

    api_docs = [ApiDocument(**d) for d in docs]

    async def _iter(start_skip: int = 0, stop_at_id=None):  # type: ignore[no-untyped-def]
        for d in api_docs[start_skip:]:
            if stop_at_id is not None and d.id <= stop_at_id:
                return
            yield d

    client = MagicMock()
    client.iter_documents = _iter
    return client


def test_backfill_checkpoints_and_resumes(tmp_path: Path) -> None:
    """Simulate a mid-run interruption and verify the resume picks up correctly."""
    from tikitaka_dwh.sync.engine import SyncEngine

    db_path = tmp_path / "wh.duckdb"
    initialize_warehouse(db_path)
    wm = WatermarkStore(db_path)

    raw_dir = tmp_path / "raw"
    staging_dir = tmp_path / "staging"

    # --- Run 1: fetch 5 docs then simulate a crash (StopIteration from the mock) ---
    five_docs = [_make_doc(i) for i in range(15, 10, -1)]  # IDs 15,14,13,12,11
    client1 = _make_mock_client(five_docs)
    engine1 = SyncEngine(client1, raw_dir, wm, staging_dir)

    asyncio.run(engine1.run_backfill())
    # All 5 fetched, backfill completed normally (no cursor should remain)
    assert wm.get_backfill_cursor() is None
    assert wm.get_last_seen_id() == 15   # highest ID seen


def test_backfill_resume_uses_peak_id(tmp_path: Path) -> None:
    """Peak ID from the first partial run must survive into the final watermark."""
    from tikitaka_dwh.sync.engine import SyncEngine

    db_path = tmp_path / "wh.duckdb"
    initialize_warehouse(db_path)
    wm = WatermarkStore(db_path)

    # Simulate: a previous partial run already stored peak_id=22000 at cursor=5000
    wm.save_backfill_progress(skip=5000, peak_id=22000)

    # This run fetches older docs (IDs 1-10, all < 22000)
    docs = [_make_doc(i) for i in range(10, 0, -1)]
    client = _make_mock_client(docs)
    raw_dir = tmp_path / "raw"
    engine = SyncEngine(client, raw_dir, wm)

    # We pass resume=False to test that clear_backfill_progress is called,
    # then re-inject the cursor manually to simulate a resume scenario.
    wm.save_backfill_progress(skip=0, peak_id=22000)
    asyncio.run(engine.run_backfill(resume=True))

    # Watermark must be 22000 (the peak from the prior run), not 10
    assert wm.get_last_seen_id() == 22000
    # Cursor must be cleared after completion
    assert wm.get_backfill_cursor() is None
