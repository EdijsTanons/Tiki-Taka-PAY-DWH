"""Sync orchestrator: backfill and incremental modes."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tikitaka_dwh.api.client import TikitakaClient
from tikitaka_dwh.sync.raw_writer import RawWriter
from tikitaka_dwh.sync.watermark import WatermarkStore

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, Optional[int]], None]


def _noop_progress(done: int, total: Optional[int]) -> None:
    pass


class SyncEngine:
    def __init__(
        self,
        client: TikitakaClient,
        raw_dir: Path,
        watermark: WatermarkStore,
        staging_dir: Optional[Path] = None,
    ) -> None:
        self._client = client
        self._raw_dir = raw_dir
        self._watermark = watermark
        self._staging_dir = staging_dir

    def _flush_staging(self, page_buf: list[dict], run_id: str, seq: int) -> None:  # type: ignore[type-arg]
        if not self._staging_dir:
            return
        try:
            from tikitaka_dwh.transform.documents import build_documents, write_documents_staging
            from tikitaka_dwh.transform.sale_lines import build_sale_lines, write_sale_lines_staging
            from tikitaka_dwh.transform.payments import build_payments, write_payments_staging

            df_docs = build_documents(page_buf)
            write_documents_staging(df_docs, self._staging_dir, run_id, seq)
            df_lines = build_sale_lines(page_buf)
            write_sale_lines_staging(df_lines, self._staging_dir, run_id, seq)
            df_pmts = build_payments(page_buf)
            write_payments_staging(df_pmts, self._staging_dir, run_id, seq)
        except Exception:
            logger.warning("Staging Parquet write failed for seq=%d — continuing.", seq, exc_info=True)

    async def run_backfill(
        self,
        progress: ProgressCallback = _noop_progress,
    ) -> int:
        run_id = uuid.uuid4().hex
        writer = RawWriter(self._raw_dir, run_id)
        self._watermark.mark_sync_started()

        count = 0
        seq = 0
        max_id: Optional[int] = None
        page_buf: list[dict] = []  # type: ignore[type-arg]

        async for doc in self._client.iter_documents():
            page_buf.append(doc.model_dump())
            if max_id is None or doc.id > max_id:
                max_id = doc.id
            count += 1
            if len(page_buf) >= 200:
                writer.write_page(page_buf)
                self._flush_staging(page_buf, run_id, seq)
                seq += 1
                page_buf = []
                progress(count, None)

        if page_buf:
            writer.write_page(page_buf)
            self._flush_staging(page_buf, run_id, seq)

        if max_id is not None:
            self._watermark.set_last_seen_id(max_id)
        self._watermark.mark_sync_completed()
        progress(count, count)
        logger.info("Backfill complete: %d documents, max_id=%s", count, max_id)
        return count

    async def run_incremental(
        self,
        progress: ProgressCallback = _noop_progress,
    ) -> int:
        last_id = self._watermark.get_last_seen_id()
        if last_id is None:
            logger.info("No watermark — falling back to full backfill.")
            return await self.run_backfill(progress=progress)

        run_id = uuid.uuid4().hex
        writer = RawWriter(self._raw_dir, run_id)
        self._watermark.mark_sync_started()

        count = 0
        seq = 0
        max_id: Optional[int] = None
        page_buf: list[dict] = []  # type: ignore[type-arg]

        async for doc in self._client.iter_documents(stop_at_id=last_id):
            page_buf.append(doc.model_dump())
            if max_id is None or doc.id > max_id:
                max_id = doc.id
            count += 1
            if len(page_buf) >= 200:
                writer.write_page(page_buf)
                self._flush_staging(page_buf, run_id, seq)
                seq += 1
                page_buf = []
                progress(count, None)

        if page_buf:
            writer.write_page(page_buf)
            self._flush_staging(page_buf, run_id, seq)

        if max_id is not None:
            self._watermark.set_last_seen_id(max_id)
        self._watermark.mark_sync_completed()
        progress(count, count)
        logger.info("Incremental sync complete: %d new documents, max_id=%s", count, max_id)
        return count
