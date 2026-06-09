"""Logging configuration: rotating JSON file log + stderr WARNING handler."""

from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path
from typing import Any, ClassVar

_CONFIGURED = False


class _AuthScrubFilter(logging.Filter):
    """Redact credentials from log records.

    Covers both dict-style and positional %-args plus the message itself —
    most call sites use ``logger.info("… %s", value)``, which a key-based
    dict filter alone would never touch.
    """

    _KEYS: ClassVar[set[str]] = {"Authorization", "client_secret", "access_token", "password"}
    _TEXT_PATTERNS: ClassVar[tuple[re.Pattern[str], ...]] = (
        re.compile(r"(?i)\b(bearer\s+)[a-z0-9._~+/=-]+"),
        re.compile(r"\beyJ[\w-]{8,}\.[\w-]+\.[\w-]*"),  # bare JWT
    )

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, dict):
            record.args = {
                k: ("***REDACTED***" if k in self._KEYS else self._scrub_value(v))
                for k, v in record.args.items()
            }
        elif isinstance(record.args, tuple):
            record.args = tuple(self._scrub_value(a) for a in record.args)
        if isinstance(record.msg, str):
            record.msg = self._scrub_text(record.msg)
        return True

    def _scrub_value(self, value: Any) -> Any:
        return self._scrub_text(value) if isinstance(value, str) else value

    def _scrub_text(self, text: str) -> str:
        for pattern in self._TEXT_PATTERNS:
            text = pattern.sub(
                lambda m: (m.group(1) if m.groups() else "") + "***REDACTED***", text
            )
        return text


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json
        import traceback

        data: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = traceback.format_exception(*record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def configure_logging(log_dir: Path | None = None, level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    if log_dir is None:
        from tikitaka_dwh.config import get_settings

        log_dir = get_settings().app_data_dir / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_JsonFormatter())
    file_handler.addFilter(_AuthScrubFilter())
    root.addHandler(file_handler)

    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    stderr_handler.addFilter(_AuthScrubFilter())
    root.addHandler(stderr_handler)
