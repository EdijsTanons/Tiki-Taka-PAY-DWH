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

# Save a resume checkpoint every this many documents.  At 200 docs/page that
# is 5 pages, so a sleep-interrupted sync loses at most ~1 000 docs of work.
_CHECKPOINT_EVERY = 1_000


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
        from tikitaka_dwh.transform.documents import build_documents, write_documents_staging
        from tikitaka_dwh.transform.sale_lines import build_sale_lines, write_sale_lines_staging
        from tikitaka_dwh.transform.payments import build_payments, write_payments_staging

        df_docs = build_documents(page_buf)
        write_documents_staging(df_docs, self._staging_dir, run_id, seq)
        df_lines = build_sale_lines(page_buf)
        write_sale_lines_staging(df_lines, self._staging_dir, run_id, seq)
        df_pmts = build_payments(page_buf)
        write_payments_staging(df_pmts, self._staging_dir, run_id, seq)

    async def run_backfill(
        self,
        progress: ProgressCallback = _noop_progress,
        resume: bool = True,
    ) -> int:
        """Download all documents from the API and stage them.

        If *resume* is True (default) and a previous backfill was interrupted,
        the download continues from the saved skip cursor instead of restarting
        from document 1.  A checkpoint is written every :data:`_CHECKPOINT_EVERY`
        documents so that a sleep / network interruption loses at most that many
        docs of work.

        Because the API returns documents in **descending** ID order (newest
        first), a resumed run fetches *older* documents with *lower* IDs.  The
        watermark is therefore set to the maximum ID seen across **all** partial
        runs (stored via :py:meth:`~WatermarkStore.save_backfill_progress`).
        """
        # --- pick up where we left off, or start fresh ---
        start_skip = 0
        if resume:
            saved_cursor = self._watermark.get_backfill_cursor()
            if saved_cursor:
                logger.info("Resuming backfill from API skip=%d", saved_cursor)
                start_skip = saved_cursor
        else:
            self._watermark.clear_backfill_progress()

        run_id = uuid.uuid4().hex
        writer = RawWriter(self._raw_dir, run_id)
        self._watermark.mark_sync_started()

        count = 0          # docs fetched in this call
        seq = 0
        cur_max_id: Optional[int] = None   # highest ID seen in this call
        page_buf: list[dict] = []  # type: ignore[type-arg]

        async for doc in self._client.iter_documents(start_skip=start_skip):
            page_buf.append(doc.model_dump())
            if cur_max_id is None or doc.id > cur_max_id:
                cur_max_id = doc.id
            count += 1

            if len(page_buf) >= 200:
                writer.write_page(page_buf)
                self._flush_staging(page_buf, run_id, seq)
                seq += 1
                page_buf = []
                progress(start_skip + count, None)

                # Persist a resume checkpoint so a sleep/crash loses ≤ 1 000 docs
                if count % _CHECKPOINT_EVERY == 0 and cur_max_id is not None:
                    self._watermark.save_backfill_progress(
                        skip=start_skip + count,
                        peak_id=cur_max_id,
                    )
                    logger.debug("Checkpoint: skip=%d, peak_id=%d", start_skip + count, cur_max_id)

        if page_buf:
            writer.write_page(page_buf)
            self._flush_staging(page_buf, run_id, seq)

        # The true watermark = highest ID across all partial runs.
        # The first run fetches the newest (highest) docs; resumed runs fetch
        # older (lower) docs — so we must not overwrite with the resumed max.
        peak_from_prev = self._watermark.get_backfill_peak_id()
        candidates = [x for x in (cur_max_id, peak_from_prev) if x is not None]
        final_max_id: Optional[int] = max(candidates) if candidates else None

        if final_max_id is not None:
            self._watermark.set_last_seen_id(final_max_id)

        self._watermark.clear_backfill_progress()
        self._watermark.mark_sync_completed()
        progress(start_skip + count, start_skip + count)
        logger.info(
            "Backfill complete: %d docs in this run (total offset %d), max_id=%s",
            count, start_skip + count, final_max_id,
        )
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
