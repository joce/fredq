"""Async FRED client that returns raw response bodies."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Final, Literal

import httpx2 as httpx
import regex
from typing_extensions import override

from fredq import __version__
from fredq.exceptions import (
    FredClientUsageError,
    FredRequestError,
    FredUnavailableError,
)

if TYPE_CHECKING:
    from fredq.types import ParamValue

# Public constant so commands.py and tests can reference the base URL without
# importing the full class.  Moved from CommandSpec.base_url (B2).
FRED_BASE_URL: Final[str] = "https://api.stlouisfed.org"

_API_KEY_PATTERN: Final[str] = "api_key="
_API_KEY_REDACTED: Final[str] = "api_key=[REDACTED]"
_API_KEY_RE: Final[regex.Pattern[str]] = regex.compile(r"api_key=[^&\s\"']+")

# Module-level guard: install the redact filter at most once so that creating
# multiple FredClient instances does not stack duplicate filters on handlers.
_redact_filter_installed: bool = False


class _ApiKeyRedactFilter(logging.Filter):
    """Logging filter that strips ``api_key=<value>`` from all log records.

    Attached to *handlers* (not loggers) so that every record that reaches
    a handler — regardless of which child logger emitted it — is scrubbed.
    This survives httpx2 splitting its logging across child loggers in future
    versions.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the API key from the log record message and exception text.

        Returns:
            bool: Always ``True`` (the record is never suppressed).
        """

        message = record.getMessage()
        if _API_KEY_PATTERN in message:
            record.msg = _API_KEY_RE.sub(_API_KEY_REDACTED, message)
            record.args = ()

        # Also scrub exception text if present — a logger.exception() call
        # could embed a URL (including the api_key param) in the traceback.
        if record.exc_text and _API_KEY_PATTERN in record.exc_text:
            record.exc_text = _API_KEY_RE.sub(_API_KEY_REDACTED, record.exc_text)

        return True


def _install_api_key_redact_filter() -> None:
    """Attach :class:`_ApiKeyRedactFilter` to all handlers of relevant loggers.

    Filters on *handlers* apply to every record that reaches the handler,
    regardless of which logger originally emitted it.  This is more robust
    than filtering the logger itself because it survives httpx2 adding child
    loggers (e.g. ``httpx2.client``) in future releases.

    The function is idempotent: the module-level ``_redact_filter_installed``
    flag prevents duplicate filters when multiple ``FredClient`` instances
    are created.
    """

    global _redact_filter_installed  # ruff: ignore[global-statement]
    if _redact_filter_installed:
        return

    flt = _ApiKeyRedactFilter()

    # Attach to all handlers on the root logger and the HTTP stack loggers.
    # loggers.  New handlers added after this call will not have the filter,
    # but that is acceptable: the important case is the logging.basicConfig
    # StreamHandler that is the common default.
    for logger_name in ("", "httpx2", "httpcore2"):
        logger = logging.getLogger(logger_name) if logger_name else logging.root
        for handler in logger.handlers:
            handler.addFilter(flt)
        # Also attach to the logger itself as a belt-and-suspenders guard for
        # handlers added later.
        logger.addFilter(flt)

    _redact_filter_installed = True


# Design note — why httpx2 event_hooks were NOT used for URL scrubbing
# -----------------------------------------------------------------------
# httpx2 supports ``event_hooks={"request": [callback]}`` which fires a
# callback with the live ``httpx2.Request`` object just before the request
# is sent.  The appeal is intercepting the request before httpx2 logs the
# URL.  However, this approach has a fundamental problem:
#
#   * The ``request.url`` on the ``Request`` object is what httpx2 actually
#     uses for the HTTP call.  Mutating it to strip the ``api_key`` param
#     would also strip it from the real request, breaking authentication.
#
#   * We cannot replace the URL with a redacted copy for logging purposes
#     without also affecting the in-flight request.  httpx2 has no separate
#     "URL for display" field.
#
#   * Logging a custom message from the hook and then suppressing httpx2's
#     own log lines would require patching httpx2 internals that are not
#     part of its public API.
#
# The logging filter on handlers (``_ApiKeyRedactFilter``) is the correct
# defense: it intercepts records after they are fully formatted but before
# they are written to any sink, and it is robust to httpx2's logger hierarchy
# because it is attached to the logger objects themselves as a fall-through.
#
# Future maintainers: please do not re-introduce an event_hooks scrubber;
# the above constraints have not changed.


class FredClient:
    """Async FRED API client.

    Returns the FRED response body verbatim; callers decide what to do
    with the JSON. The client injects ``api_key`` and ``file_type=json``
    on every request and redacts the API key from any error message.
    """

    _FRED_BASE_URL: Final[str] = FRED_BASE_URL
    _USER_AGENT: Final[str] = f"fredq/{__version__} (+https://github.com/joce/fredq)"
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
            timeout: Optional custom httpx2 timeout configuration.
            base_url: Override the FRED base URL (useful for tests).
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
        _install_api_key_redact_filter()

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
        **kwargs: Any,  # ruff: ignore[any-type]
    ) -> httpx.Response:
        attempt = 1
        while True:
            try:
                response = await self._client.request(method, url, **kwargs)
                if response.is_error:
                    response.raise_for_status()
            except httpx.HTTPStatusError as exc:  # ruff: ignore[try-except-in-loop]
                status_code = exc.response.status_code if exc.response else -1
                if (
                    status_code in self._RETRYABLE_STATUS_CODES
                    and attempt < self._REQUEST_ATTEMPTS
                ):
                    await asyncio.sleep(self._RETRY_DELAY_SECONDS * attempt)
                    attempt += 1
                    continue
                url_str = self._redact_url(exc.request.url)
                body = _API_KEY_RE.sub(_API_KEY_REDACTED, exc.response.text)
                raise FredRequestError(status_code, url_str, body=body) from exc
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

        Raises:
            FredClientUsageError: If ``params`` contains ``api_key`` or
                ``file_type``.
        """

        reserved_keys: frozenset[str] = frozenset({"api_key", "file_type"})
        forbidden = reserved_keys & params.keys()
        if forbidden:
            keys_str = ", ".join(sorted(forbidden))
            message = (
                f"caller must not supply reserved parameter(s): {keys_str}; "
                "fredq injects them automatically"
            )
            raise FredClientUsageError(message)
        request_params: dict[str, ParamValue] = dict(params)
        request_params["api_key"] = self._api_key
        request_params["file_type"] = "json"
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
