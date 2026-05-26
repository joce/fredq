"""Tests for the FRED HTTP client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
import pytest
from typing_extensions import override

from fredq.client import (
    FredClient,
    _ApiKeyRedactFilter,  # pyright: ignore[reportPrivateUsage]
)
from fredq.exceptions import (
    FredClientUsageError,
    FredRequestError,
    FredUnavailableError,
)

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


# C2 — additional client coverage


@pytest.mark.asyncio
async def test_transport_error_raises_fred_unavailable(httpx_mock: HTTPXMock) -> None:
    """TransportError exhausted → FredUnavailableError (not a raw httpx error)."""

    url = (
        "https://api.stlouisfed.org/fred/series?"
        "series_id=GNPCA&api_key=secret&file_type=json"
    )
    # Simulate a transport-level failure on every attempt.
    for _ in range(REQUEST_ATTEMPTS):
        httpx_mock.add_exception(httpx.ConnectError("connection refused"), url=url)

    client = FredClient(api_key="secret")
    try:
        with pytest.raises(FredUnavailableError):
            await client.get("/fred/series", {"series_id": "GNPCA"})
    finally:
        await client.aclose()

    assert len(httpx_mock.get_requests()) == REQUEST_ATTEMPTS


@pytest.mark.asyncio
async def test_4xx_not_retried(httpx_mock: HTTPXMock) -> None:
    """4xx errors are not retried — they fail immediately on the first attempt."""

    url = (
        "https://api.stlouisfed.org/fred/series?"
        "series_id=GNPCA&api_key=secret&file_type=json"
    )
    httpx_mock.add_response(method="GET", url=url, status_code=401)

    client = FredClient(api_key="secret")
    try:
        with pytest.raises(FredRequestError) as exc_info:
            await client.get("/fred/series", {"series_id": "GNPCA"})
    finally:
        await client.aclose()

    http_unauthorized = 401
    assert exc_info.value.status_code == http_unauthorized
    # Only one request should have been made (no retries).
    assert len(httpx_mock.get_requests()) == 1


@pytest.mark.asyncio
async def test_fred_unavailable_error_message_is_safe(httpx_mock: HTTPXMock) -> None:
    """FredUnavailableError message uses context, never the api_key."""

    url = (
        "https://api.stlouisfed.org/fred/series?"
        "series_id=GNPCA&api_key=super-secret&file_type=json"
    )
    for _ in range(REQUEST_ATTEMPTS):
        httpx_mock.add_exception(httpx.ConnectError("connection refused"), url=url)

    client = FredClient(api_key="super-secret")
    try:
        with pytest.raises(FredUnavailableError) as exc_info:
            await client.get("/fred/series", {"series_id": "GNPCA"})
    finally:
        await client.aclose()

    msg = str(exc_info.value)
    assert "super-secret" not in msg
    assert "api call: /fred/series" in msg


# Item 1 — _ApiKeyRedactFilter tests


def test_redact_filter_scrubs_child_logger_message() -> None:
    """Filter on a handler scrubs api_key even when emitted by a child logger."""

    # Create a handler with the filter and a child logger pointing at it.
    stream_records: list[logging.LogRecord] = []

    class _CapturingHandler(logging.Handler):
        @override
        def emit(self, record: logging.LogRecord) -> None:
            stream_records.append(record)

    handler = _CapturingHandler()
    handler.addFilter(_ApiKeyRedactFilter())

    child_logger = logging.getLogger("httpx.client")
    child_logger.addHandler(handler)
    child_logger.setLevel(logging.DEBUG)
    child_logger.propagate = False

    try:
        child_logger.info(
            "HTTP Request: GET https://api.stlouisfed.org/fred/series?series_id=GNPCA&api_key=secret&file_type=json"
        )
    finally:
        child_logger.removeHandler(handler)
        child_logger.propagate = True

    assert len(stream_records) == 1
    formatted = stream_records[0].getMessage()
    assert "secret" not in formatted
    assert "api_key=[REDACTED]" in formatted


def test_redact_filter_scrubs_exception_text() -> None:
    """Filter scrubs api_key that appears in exc_text (from logger.exception)."""

    flt = _ApiKeyRedactFilter()

    record = logging.LogRecord(
        name="fredq.client",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="Request failed",
        args=(),
        exc_info=None,
    )
    # Simulate formatted exception text containing a URL with api_key.
    record.exc_text = (
        "Traceback (most recent call last):\n"
        "  ...\n"
        "httpx.HTTPStatusError: 400 for https://api.stlouisfed.org/fred/series?"
        "series_id=GNPCA&api_key=topsecret&file_type=json"
    )

    flt.filter(record)

    assert "topsecret" not in (record.exc_text or "")
    assert "api_key=[REDACTED]" in (record.exc_text or "")


def test_redact_filter_passes_through_records_without_api_key() -> None:
    """Records without 'api_key=' in the message are passed through unchanged."""

    flt = _ApiKeyRedactFilter()
    record = logging.LogRecord(
        name="httpx",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="HTTP/1.1 200 OK",
        args=(),
        exc_info=None,
    )

    result = flt.filter(record)

    assert result is True
    assert record.getMessage() == "HTTP/1.1 200 OK"


def test_both_reserved_keys_rejected_together() -> None:
    """Passing both api_key and file_type raises and names both keys."""

    import asyncio  # noqa: PLC0415

    client = FredClient(api_key="secret")

    async def _run() -> None:
        try:
            with pytest.raises(FredClientUsageError) as exc_info:
                await client.get("/fred/series", {"file_type": "xml", "api_key": "foo"})
            msg = str(exc_info.value)
            assert "api_key" in msg
            assert "file_type" in msg
        finally:
            await client.aclose()

    asyncio.run(_run())
