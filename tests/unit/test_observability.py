"""Tests for log scrubbing and Sentry event scrubbing."""

from __future__ import annotations

import logging

from tikitaka_dwh.observability.logging import _AuthScrubFilter
from tikitaka_dwh.observability.sentry import _scrub


def _record(msg: str, args: object = None) -> logging.LogRecord:
    return logging.LogRecord("test", logging.INFO, __file__, 1, msg, args, None)  # type: ignore[arg-type]


def test_filter_redacts_bearer_token_in_positional_args() -> None:
    rec = _record("Auth header: %s", ("Bearer abc.def-123",))
    _AuthScrubFilter().filter(rec)
    msg = rec.getMessage()
    assert "abc.def-123" not in msg
    assert "***REDACTED***" in msg


def test_filter_redacts_jwt_in_message() -> None:
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJl"
    rec = _record(f"refreshed token={token}")
    _AuthScrubFilter().filter(rec)
    msg = rec.getMessage()
    assert token not in msg
    assert "***REDACTED***" in msg


def test_filter_redacts_dict_args_by_key() -> None:
    rec = _record(
        "auth=%(Authorization)s other=%(other)s",
        {"Authorization": "supersecret", "other": "visible"},
    )
    _AuthScrubFilter().filter(rec)
    msg = rec.getMessage()
    assert "supersecret" not in msg
    assert "visible" in msg


def test_filter_leaves_plain_messages_untouched() -> None:
    rec = _record("Loaded %d documents", (42,))
    _AuthScrubFilter().filter(rec)
    assert rec.getMessage() == "Loaded 42 documents"


def test_sentry_scrub_is_recursive_and_case_insensitive() -> None:
    event = {
        "request": {"headers": {"Authorization": "Bearer xyz"}},
        "breadcrumbs": [{"data": {"access_token": "tok", "keep": "yes"}}],
        "extra": {"nested": {"raw_xml": "<doc>secret</doc>", "CLIENT_SECRET": "s"}},
    }
    scrubbed = _scrub(event)
    assert scrubbed["request"]["headers"]["Authorization"] == "***REDACTED***"  # type: ignore[index]
    assert scrubbed["breadcrumbs"][0]["data"]["access_token"] == "***REDACTED***"  # type: ignore[index]
    assert scrubbed["breadcrumbs"][0]["data"]["keep"] == "yes"  # type: ignore[index]
    assert scrubbed["extra"]["nested"]["raw_xml"] == "***REDACTED***"  # type: ignore[index]
    assert scrubbed["extra"]["nested"]["CLIENT_SECRET"] == "***REDACTED***"  # type: ignore[index]
