"""Tests for TokenProvider — expiry-triggered refresh and 401 invalidation."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from tikitaka_dwh.auth import TokenProvider


def _make_jwt(exp: float) -> str:
    import base64
    import json

    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload_data = {"exp": int(exp), "sub": "test"}
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}."


@pytest.fixture()
def base_url() -> str:
    return "https://api.manage.tikitaka.lv"


@pytest.fixture()
def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient()


@respx.mock
@pytest.mark.asyncio
async def test_token_fetched_on_first_call(base_url: str, http_client: httpx.AsyncClient):
    future_exp = time.time() + 3600
    token = _make_jwt(future_exp)
    respx.post(f"{base_url}/clients/token").mock(
        return_value=httpx.Response(200, json={"access_token": token, "token_type": "bearer"})
    )
    provider = TokenProvider(
        lambda: "cid", lambda: "csec", base_url, http_client
    )
    result = await provider.get_token()
    assert result == token
    assert respx.calls.call_count == 1


@respx.mock
@pytest.mark.asyncio
async def test_token_cached_within_ttl(base_url: str, http_client: httpx.AsyncClient):
    future_exp = time.time() + 3600
    token = _make_jwt(future_exp)
    respx.post(f"{base_url}/clients/token").mock(
        return_value=httpx.Response(200, json={"access_token": token, "token_type": "bearer"})
    )
    provider = TokenProvider(lambda: "cid", lambda: "csec", base_url, http_client)
    t1 = await provider.get_token()
    t2 = await provider.get_token()
    assert t1 == t2
    assert respx.calls.call_count == 1  # only one network call


@respx.mock
@pytest.mark.asyncio
async def test_token_refreshed_when_expired(base_url: str, http_client: httpx.AsyncClient):
    expired_exp = time.time() - 10  # already expired
    expired_token = _make_jwt(expired_exp)
    fresh_exp = time.time() + 3600
    fresh_token = _make_jwt(fresh_exp)

    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        tok = expired_token if call_count == 1 else fresh_token
        return httpx.Response(200, json={"access_token": tok, "token_type": "bearer"})

    respx.post(f"{base_url}/clients/token").mock(side_effect=side_effect)

    provider = TokenProvider(lambda: "cid", lambda: "csec", base_url, http_client)
    t1 = await provider.get_token()
    assert t1 == expired_token

    # invalidate so next call re-fetches
    provider.invalidate()
    t2 = await provider.get_token()
    assert t2 == fresh_token
    assert call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_invalidate_forces_refresh(base_url: str, http_client: httpx.AsyncClient):
    future_exp = time.time() + 3600
    token_a = _make_jwt(future_exp)
    token_b = _make_jwt(future_exp)

    tokens = iter([token_a, token_b])
    respx.post(f"{base_url}/clients/token").mock(
        side_effect=lambda req: httpx.Response(
            200, json={"access_token": next(tokens), "token_type": "bearer"}
        )
    )
    provider = TokenProvider(lambda: "cid", lambda: "csec", base_url, http_client)
    first = await provider.get_token()
    provider.invalidate()
    second = await provider.get_token()
    assert first == token_a
    assert second == token_b
