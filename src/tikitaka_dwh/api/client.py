"""Tikitaka API HTTP client with retry, re-auth, and pagination."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional

import httpx

from tikitaka_dwh.api.schemas import ApiDocument, ApiListResponse
from tikitaka_dwh.auth import TokenProvider

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 200
_MAX_RETRIES = 3
_RETRY_STATUSES = {500, 502, 503, 504}
# Per-request timeout: generous read timeout because the API generates pages
# server-side and can be slow on large data sets.
_REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)


class TikitakaClient:
    def __init__(
        self,
        base_url: str,
        token_provider: TokenProvider,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def fetch_documents_page(
        self,
        skip: int = 0,
        limit: int = _DEFAULT_LIMIT,
    ) -> ApiListResponse:
        url = f"{self._base_url}/clients/device/extended_analytics_combined_documents"
        params = {
            "skip_total": "false",
            "skip": str(skip),
            "limit": str(limit),
            "order": "DESC",
            "in_url": "false",
        }
        return await self._get_with_retry(url, params)

    async def _get_with_retry(
        self,
        url: str,
        params: dict[str, str],
        max_retries: int = _MAX_RETRIES,
    ) -> ApiListResponse:
        last_exc: Optional[Exception] = None
        reauthed = False
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            token = await self._token_provider.get_token()
            headers = {"Authorization": f"Bearer {token}"}
            try:
                resp = await self._http.get(url, params=params, headers=headers, timeout=_REQUEST_TIMEOUT)
            except httpx.TransportError as exc:
                last_exc = exc
                logger.warning("Network error on attempt %d: %s", attempt, exc)
                await asyncio.sleep(2 ** (attempt - 1))
                continue

            if resp.status_code == 401 and not reauthed:
                logger.info("401 received — invalidating token and retrying once.")
                self._token_provider.invalidate()
                reauthed = True
                attempt -= 1  # don't count the 401 as a retry attempt
                continue

            if resp.status_code in _RETRY_STATUSES:
                logger.warning("HTTP %d on attempt %d, retrying.", resp.status_code, attempt)
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
                await asyncio.sleep(2 ** (attempt - 1))
                continue

            resp.raise_for_status()
            return ApiListResponse.model_validate(resp.json())

        raise last_exc or RuntimeError("All retries exhausted")

    async def _fetch_with_500_fallback(
        self,
        skip: int,
        limit: int,
    ) -> "ApiListResponse | None":
        """Fetch a page, returning None if the API returns 500 even for limit=1.

        Uses a single retry (no exponential backoff) in isolation mode so that
        the caller can quickly skip over a broken range without waiting minutes.
        """
        url = f"{self._base_url}/clients/device/extended_analytics_combined_documents"
        params = {
            "skip_total": "false",
            "skip": str(skip),
            "limit": str(limit),
            "order": "DESC",
            "in_url": "false",
        }
        try:
            return await self._get_with_retry(url, params, max_retries=1)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 500:
                raise
            if limit == 1:
                return None
            # Shrink to 1 and try once more with a single attempt.
            params["limit"] = "1"
            try:
                return await self._get_with_retry(url, params, max_retries=1)
            except httpx.HTTPStatusError as exc2:
                if exc2.response.status_code == 500:
                    return None
                raise

    async def iter_documents(
        self,
        start_skip: int = 0,
        stop_at_id: Optional[int] = None,
    ) -> AsyncIterator[ApiDocument]:
        skip = start_skip
        total: Optional[int] = None
        limit = _DEFAULT_LIMIT
        # Tracks how many consecutive single-document failures we've seen so
        # we can skip ahead rather than grinding through a corrupt range.
        consecutive_skips = 0

        while True:
            if limit < _DEFAULT_LIMIT:
                # In recovery mode: use a fast path that drops straight to
                # limit=1 on 500 without burning retries on large pages.
                page = await self._fetch_with_500_fallback(skip, limit)
                if page is None:
                    consecutive_skips += 1
                    logger.warning(
                        "HTTP 500 for document at skip=%d — skipping (%d consecutive).",
                        skip, consecutive_skips,
                    )
                    skip += 1
                    if consecutive_skips >= 50:
                        logger.error(
                            "50 consecutive HTTP 500s starting near skip=%d — "
                            "large corrupt range on API server, skipping ahead by 200.",
                            skip - 50,
                        )
                        skip += 200
                        consecutive_skips = 0
                        limit = _DEFAULT_LIMIT
                    continue
            else:
                # Normal mode: use the full retry logic.
                try:
                    page = await self.fetch_documents_page(skip=skip, limit=limit)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 500:
                        logger.warning(
                            "HTTP 500 at skip=%d with limit=%d — entering recovery mode.",
                            skip, limit,
                        )
                        limit = 1
                        continue
                    raise

            consecutive_skips = 0

            if total is None:
                total = page.total
                logger.info("Total documents reported by API: %d", total)

            if not page.results:
                if limit < _DEFAULT_LIMIT:
                    # May just be a partial page — try advancing.
                    skip += limit
                    limit = min(limit * 4, _DEFAULT_LIMIT)
                    continue
                break

            # Gradually restore limit after successful fetches in recovery mode.
            if limit < _DEFAULT_LIMIT:
                limit = min(limit * 4, _DEFAULT_LIMIT)

            for doc in page.results:
                if stop_at_id is not None and doc.id <= stop_at_id:
                    return
                yield doc

            skip += len(page.results)
            if skip >= (total or 0):
                break
