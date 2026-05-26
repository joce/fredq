"""Tests for the FRED HTTP client."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from fredq.client import FredClient
from fredq.exceptions import FredClientUsageError, FredRequestError

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock

REQUEST_ATTEMPTS = 3


@pytest.mark.asyncio
async def test_get_injects_api_key_and_file_type(httpx_mock: HTTPXMock) -> None:
    """Every call carries an api_key and defaults file_type=json."""

    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series?"
            "series_id=GNPCA&api_key=secret&file_type=json"
        ),
        text='{"seriess": []}',
    )
    client = FredClient(api_key="secret")
    try:
        body = await client.get("/fred/series", {"series_id": "GNPCA"})
    finally:
        await client.aclose()

    assert body == '{"seriess": []}'


@pytest.mark.asyncio
async def test_get_redacts_api_key_from_request_error(
    httpx_mock: HTTPXMock,
) -> None:
    """Failed requests do not expose the API key in user-facing errors."""

    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series?"
            "series_id=GNPCA&api_key=secret-key&file_type=json"
        ),
        status_code=400,
        text='{"error_message": "Bad Request"}',
    )
    client = FredClient(api_key="secret-key")

    try:
        with pytest.raises(FredRequestError) as exc_info:
            await client.get("/fred/series", {"series_id": "GNPCA"})
    finally:
        await client.aclose()

    assert "secret-key" not in str(exc_info.value)
    assert "api_key=" not in str(exc_info.value)
    assert "series_id=GNPCA" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_rejects_caller_supplied_api_key() -> None:
    """Passing api_key in params raises FredClientUsageError immediately."""

    client = FredClient(api_key="secret")
    try:
        with pytest.raises(FredClientUsageError, match="api_key"):
            await client.get("/fred/series", {"api_key": "other"})
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_rejects_caller_supplied_file_type() -> None:
    """Passing file_type in params raises FredClientUsageError immediately."""

    client = FredClient(api_key="secret")
    try:
        with pytest.raises(FredClientUsageError, match="file_type"):
            await client.get("/fred/series", {"file_type": "xml"})
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_retries_retryable_status_codes(httpx_mock: HTTPXMock) -> None:
    """Retryable status codes are retried up to the configured attempt budget."""

    url = (
        "https://api.stlouisfed.org/fred/series?"
        "series_id=GNPCA&api_key=secret&file_type=json"
    )
    httpx_mock.add_response(method="GET", url=url, status_code=503)
    httpx_mock.add_response(method="GET", url=url, status_code=503)
    httpx_mock.add_response(method="GET", url=url, text='{"ok": true}')
    client = FredClient(api_key="secret")

    try:
        body = await client.get("/fred/series", {"series_id": "GNPCA"})
    finally:
        await client.aclose()

    assert body == '{"ok": true}'
    assert len(httpx_mock.get_requests()) == REQUEST_ATTEMPTS
