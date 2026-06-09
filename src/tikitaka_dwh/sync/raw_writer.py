"""Append-only raw JSON writer — persists one file per API page."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RawWriter:
    def __init__(self, raw_dir: Path, run_id: str) -> None:
        self._raw_dir = raw_dir
        self._run_id = run_id
        self._seq = 0

    def write_page(self, docs: list[dict[str, Any]], page_date: datetime | None = None) -> Path:
        dt = (page_date or datetime.now(UTC)).strftime("%Y-%m-%d")
        dest_dir = self._raw_dir / f"dt={dt}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"page_{self._run_id}_{self._seq:04d}.json"
        path.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
        self._seq += 1
        logger.debug("Wrote raw page to %s (%d docs)", path, len(docs))
        return path
