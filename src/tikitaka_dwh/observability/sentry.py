"""Sentry error reporting — opt-in, scrubbed."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_SCRUB_KEYS = {
    "authorization",
    "client_secret",
    "access_token",
    "customer_card_number",
    "client_reg_number",
    "card_pan",
    "raw_xml",
    "password",
}


def _scrub(obj: object) -> object:
    """Recursively mask sensitive keys anywhere in the event payload.

    Headers alone are not enough — tokens and raw XML can also appear in
    breadcrumbs, extra context and exception values.
    """
    if isinstance(obj, dict):
        return {
            k: "***REDACTED***"
            if isinstance(k, str) and k.lower() in _SCRUB_KEYS
            else _scrub(v)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_scrub(item) for item in obj]
    return obj


def _before_send(event: dict, hint: object) -> dict | None:  # type: ignore[type-arg]
    return _scrub(event)  # type: ignore[return-value]


def init_sentry(dsn: str | None = None) -> None:
    resolved_dsn = dsn or os.environ.get("TIKITAKA_SENTRY_DSN") or _settings_dsn()
    if not resolved_dsn:
        logger.debug("Sentry DSN not set — crash reporting disabled.")
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=resolved_dsn,
            # dict-based hook works at runtime; the stub wants sentry's Event TypedDict
            before_send=_before_send,  # type: ignore[arg-type]
            traces_sample_rate=0.0,
            send_default_pii=False,
            # Local variables in stack traces can contain tokens and card data
            include_local_variables=False,
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
