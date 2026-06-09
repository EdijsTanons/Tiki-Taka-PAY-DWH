"""Tests for the API client: pagination, retry, re-auth, 500 recovery."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from tikitaka_dwh.api.client import TikitakaClient
from tikitaka_dwh.auth import TokenProvider

BASE = "https://api.test.local"
DOCS_URL = f"{BASE}/clients/device/extended_analytics_combined_documents"
TOKEN_URL = f"{BASE}/clients/token"


@pytest.fixture()
def fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the client's exponential backoff instant."""

    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", _instant)


@pytest.fixture()
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


def _make_client(http: httpx.AsyncClient) -> TikitakaClient:
    provider = TokenProvider(lambda: "user", lambda: "pass", base_url=BASE, http_client=http)
    return TikitakaClient(BASE, provider, http)


def _mock_token(respx_mock: respx.MockRouter) -> respx.Route:
    return respx_mock.post(TOKEN_URL).respond(
        200, json={"access_token": "tok", "expires_in": 3600}
    )


def _paged_serve(docs: list[dict], total: int):  # type: ignore[type-arg, no-untyped-def]
    def _serve(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        skip, limit = int(params["skip"]), int(params["limit"])
        return httpx.Response(200, json={"total": total, "results": docs[skip : skip + limit]})

    return _serve


async def test_iter_documents_paginates_descending(http: httpx.AsyncClient) -> None:
    docs = [{"id": i} for i in range(400, 0, -1)]  # two full pages of 200
    with respx.mock(assert_all_called=False) as respx_mock:
        _mock_token(respx_mock)
        respx_mock.get(DOCS_URL).mock(side_effect=_paged_serve(docs, total=400))

        client = _make_client(http)
        got = [d.id async for d in client.iter_documents()]

    assert got == list(range(400, 0, -1))


async def test_iter_documents_stops_at_watermark(http: httpx.AsyncClient) -> None:
    docs = [{"id": i} for i in range(10, 0, -1)]
    with respx.mock(assert_all_called=False) as respx_mock:
        _mock_token(respx_mock)
        respx_mock.get(DOCS_URL).mock(side_effect=_paged_serve(docs, total=10))

        client = _make_client(http)
        got = [d.id async for d in client.iter_documents(stop_at_id=7)]

    # Only documents NEWER than the watermark (id > 7) are yielded
    assert got == [10, 9, 8]


async def test_retry_on_500_then_success(http: httpx.AsyncClient, fast_sleep: None) -> None:
    page = {"total": 1, "results": [{"id": 1}]}
    with respx.mock(assert_all_called=False) as respx_mock:
        _mock_token(respx_mock)
        route = respx_mock.get(DOCS_URL)
        route.side_effect = [httpx.Response(500), httpx.Response(200, json=page)]

        client = _make_client(http)
        result = await client.fetch_documents_page()

    assert route.call_count == 2
    assert [d.id for d in result.results] == [1]


async def test_401_invalidates_token_and_retries(http: httpx.AsyncClient) -> None:
    page = {"total": 1, "results": [{"id": 1}]}
    with respx.mock(assert_all_called=False) as respx_mock:
        token_route = _mock_token(respx_mock)
        route = respx_mock.get(DOCS_URL)
        route.side_effect = [httpx.Response(401), httpx.Response(200, json=page)]

        client = _make_client(http)
        result = await client.fetch_documents_page()

    assert result.total == 1
    # A fresh token must have been fetched after the 401
    assert token_route.call_count == 2


async def test_iter_documents_skips_poisoned_document(
    http: httpx.AsyncClient, fast_sleep: None
) -> None:
    """A document the API can't serve (500 even at limit=1) is skipped, not fatal."""
    docs = [{"id": 3}, {"id": 2}, {"id": 1}]  # the doc at skip=1 (id=2) is poisoned

    def _serve(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        skip, limit = int(params["skip"]), int(params["limit"])
        if skip == 1 or (skip == 0 and limit > 1):
            return httpx.Response(500)
        return httpx.Response(200, json={"total": 3, "results": docs[skip : skip + limit]})

    with respx.mock(assert_all_called=False) as respx_mock:
        _mock_token(respx_mock)
        respx_mock.get(DOCS_URL).mock(side_effect=_serve)

        client = _make_client(http)
        got = [d.id async for d in client.iter_documents()]

    assert got == [3, 1]
