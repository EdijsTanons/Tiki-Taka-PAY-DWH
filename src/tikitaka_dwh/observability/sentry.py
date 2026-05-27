"""Sentry error reporting — opt-in, scrubbed."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_SCRUB_KEYS = {
    "Authorization",
    "client_secret",
    "access_token",
    "customer_card_number",
    "client_reg_number",
    "card_pan",
    "raw_xml",
    "password",
}


def _before_send(event: dict, hint: object) -> dict | None:  # type: ignore[type-arg]
    for key in list(event.get("request", {}).get("headers", {}).keys()):
        if key in _SCRUB_KEYS:
            event["request"]["headers"][key] = "***REDACTED***"
    return event


def init_sentry(dsn: str | None = None) -> None:
    resolved_dsn = dsn or os.environ.get("TIKITAKA_SENTRY_DSN") or _settings_dsn()
    if not resolved_dsn:
        logger.debug("Sentry DSN not set — crash reporting disabled.")
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=resolved_dsn,
            before_send=_before_send,
            traces_sample_rate=0.0,
        )
        logger.info("Sentry initialized.")
    except Exception:
        logger.warning("Failed to initialize Sentry.", exc_info=True)


def _settings_dsn() -> str | None:
    try:
        from tikitaka_dwh.config import get_settings

        return get_settings().sentry_dsn
    except Exception:
        return None
