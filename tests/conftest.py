"""Test fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

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


def collect_nested_extras(model: object, path: str = "$") -> list[tuple[str, str]]:
    """Recursively collect (path, key) for every unmodeled wire field.

    Walks pydantic models, lists, and dicts of models. An empty result
    means the model fully covers the payload — the zero-extras gate.

    Returns:
        list[tuple[str, str]]: One entry per extra field found.
    """

    # Keep pydantic off non-model tests.
    from pydantic import BaseModel  # ruff: ignore[import-outside-top-level]

    extras: list[tuple[str, str]] = []
    if isinstance(model, BaseModel):
        extras.extend((path, key) for key in (model.model_extra or {}))
        for name in type(model).model_fields:
            extras += collect_nested_extras(getattr(model, name), f"{path}.{name}")
    elif isinstance(model, list):
        items = cast("list[object]", model)
        for index, item in enumerate(items):
            extras += collect_nested_extras(item, f"{path}[{index}]")
    elif isinstance(model, dict):
        mapping = cast("dict[object, object]", model)
        for key, item in mapping.items():
            extras += collect_nested_extras(item, f"{path}[{key!r}]")
    return extras


def universal_keys(records: list[dict[str, object]]) -> set[str]:
    """Keys present in 100% of the given wire records.

    Returns:
        set[str]: The corpus-measured universal key set.
    """

    assert records, "no records to measure - corpus glob matched nothing"
    keys = set(records[0])
    for record in records[1:]:
        keys &= set(record)
    return keys


def required_field_names(model_cls: type[Any]) -> set[str]:
    """Field names a pydantic model requires (no default).

    Returns:
        set[str]: Required field names.
    """

    fields = cast("dict[str, Any]", model_cls.model_fields)
    return {name for name, field in fields.items() if field.is_required()}
