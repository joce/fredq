"""Test fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2 as httpx
import pytest

# cspell:words aread

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass
class _Route:
    method: str | None
    url: str
    status_code: int
    text: str | None
    exception: BaseException | None
    used: bool = False


class HTTPXMock:
    """Small httpx2 test transport used by these tests."""

    def __init__(self) -> None:
        """Initialize empty route and request stores."""

        self._routes: list[_Route] = []
        self._requests: list[httpx.Request] = []

    def add_response(
        self,
        *,
        method: str | None = None,
        url: str,
        status_code: int = 200,
        text: str | None = None,
    ) -> None:
        """Register a mocked response."""

        self._routes.append(
            _Route(
                method=method.upper() if method else None,
                url=url,
                status_code=status_code,
                text=text,
                exception=None,
            )
        )

    def add_exception(
        self,
        exception: BaseException,
        *,
        url: str,
        method: str | None = None,
    ) -> None:
        """Register an exception for a mocked request."""

        self._routes.append(
            _Route(
                method=method.upper() if method else None,
                url=url,
                status_code=0,
                text=None,
                exception=exception,
            )
        )

    def get_requests(self) -> list[httpx.Request]:
        """Return requests received by the mock transport."""

        return list(self._requests)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Serve a request from the registered routes."""

        await request.aread()
        self._requests.append(request)
        route = self._pop_route(request)
        if route is None:
            message = f"No mocked response for {request.method} {request.url}"
            raise httpx.TimeoutException(message, request=request)
        if route.exception is not None:
            raise route.exception

        return httpx.Response(
            status_code=route.status_code,
            request=request,
            extensions={"http_version": b"HTTP/1.1"},
            text=route.text,
        )

    def assert_all_used(self) -> None:
        """Fail if a registered route was never requested."""

        unused = [route for route in self._routes if not route.used]
        assert not unused, "Mocked response was not requested: " + ", ".join(
            f"{route.method or 'ANY'} {route.url}" for route in unused
        )

    def _pop_route(self, request: httpx.Request) -> _Route | None:
        for route in self._routes:
            if route.used:
                continue
            if route.method is not None and route.method != request.method:
                continue
            if route.url != str(request.url):
                continue
            route.used = True
            return route
        return None


@pytest.fixture
def httpx_mock(monkeypatch: pytest.MonkeyPatch) -> Generator[HTTPXMock]:
    """Mock httpx2 async transport requests."""

    mock = HTTPXMock()

    async def mocked_handle_async_request(
        transport: httpx.AsyncHTTPTransport,
        request: httpx.Request,
    ) -> httpx.Response:
        del transport
        return await mock.handle_async_request(request)

    monkeypatch.setattr(
        httpx.AsyncHTTPTransport,
        "handle_async_request",
        mocked_handle_async_request,
    )
    yield mock
    mock.assert_all_used()
