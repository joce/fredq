"""Async FRED client that returns raw response bodies."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Final, Literal

import httpx

from fredq.exceptions import FredRequestError, FredUnavailableError

if TYPE_CHECKING:
    from fredq.types import ParamValue


class FredClient:
    """Async FRED API client.

    Returns the FRED response body verbatim; callers decide what to do
    with the JSON. The client injects ``api_key`` and ``file_type=json``
    on every request and redacts the API key from any error message.
    """

    _FRED_BASE_URL: Final[str] = "https://api.stlouisfed.org"
    _USER_AGENT: Final[str] = "fredq/0.0.1 (+https://github.com/joce/fredq)"
    _REQUEST_ATTEMPTS: Final[int] = 3
    _RETRYABLE_STATUS_CODES: Final[frozenset[int]] = frozenset(
        {429, 500, 502, 503, 504}
    )
    _RETRY_DELAY_SECONDS: Final[float] = 0.25

    def __init__(
        self,
        api_key: str,
        *,
        timeout: httpx.Timeout | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the FRED client.

        Args:
            api_key: FRED API key used to authenticate every request.
            timeout: Optional custom httpx timeout configuration.
            base_url: Override the FRED base URL (useful for tests and for the
                future GeoFRED Maps endpoints).
        """

        self._api_key = api_key
        self._timeout = timeout or httpx.Timeout(connect=5, read=15, write=5, pool=5)
        self._base_url = base_url or self._FRED_BASE_URL
        self._client = httpx.AsyncClient(
            headers={
                "accept": "application/json",
                "user-agent": self._USER_AGENT,
            },
            timeout=self._timeout,
        )
        self._logger = logging.getLogger(__name__)

    @staticmethod
    def _redact_url(url: httpx.URL) -> str:
        params = [
            (name, value)
            for name, value in url.params.multi_items()
            if name != "api_key"
        ]
        return str(url.copy_with(params=params))

    async def _request_or_raise(
        self,
        method: Literal["GET"],
        url: str,
        *,
        context: str,
        **kwargs: Any,  # noqa: ANN401
    ) -> httpx.Response:
        attempt = 1
        while True:
            try:
                response = await self._client.request(method, url, **kwargs)
                if response.is_error:
                    response.raise_for_status()
            except httpx.HTTPStatusError as exc:  # noqa: PERF203
                status_code = exc.response.status_code if exc.response else -1
                if (
                    status_code in self._RETRYABLE_STATUS_CODES
                    and attempt < self._REQUEST_ATTEMPTS
                ):
                    await asyncio.sleep(self._RETRY_DELAY_SECONDS * attempt)
                    attempt += 1
                    continue
                url_str = self._redact_url(exc.request.url)
                raise FredRequestError(status_code, url_str) from exc
            except httpx.TransportError as exc:
                if attempt < self._REQUEST_ATTEMPTS:
                    await asyncio.sleep(self._RETRY_DELAY_SECONDS * attempt)
                    attempt += 1
                    continue
                raise FredUnavailableError(context) from exc
            else:
                return response

    async def get(
        self,
        path: str,
        params: dict[str, ParamValue],
        *,
        base_url: str | None = None,
    ) -> str:
        """Call a FRED endpoint.

        Args:
            path: Endpoint path beginning with ``/`` (e.g. ``/fred/series``).
            params: Query parameters; ``api_key`` and ``file_type`` are
                injected automatically and must not be supplied by the caller.
            base_url: Optional per-call base URL override.

        Returns:
            str: Raw FRED response body.
        """

        request_params: dict[str, ParamValue] = dict(params)
        request_params["api_key"] = self._api_key
        request_params.setdefault("file_type", "json")
        host = base_url or self._base_url
        response = await self._request_or_raise(
            "GET",
            host + path,
            context=f"api call: {path}",
            params=request_params,
        )
        return response.text

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""

        await self._client.aclose()
