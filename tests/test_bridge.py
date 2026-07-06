"""Tests for the background-loop sync bridge."""

from __future__ import annotations

import asyncio
import concurrent.futures

import pytest

from fredq._bridge import run


async def _double(value: int) -> int:
    await asyncio.sleep(0)
    return value * 2


async def _boom() -> None:  # noqa: RUF029 - coroutine required by run()'s API
    message = "kaboom"
    raise RuntimeError(message)


async def _hang() -> None:
    await asyncio.sleep(60)


def test_run_returns_coroutine_result() -> None:
    """run() executes the coroutine and returns its value."""

    assert run(_double(21)) == 42  # noqa: PLR2004


def test_run_propagates_exceptions() -> None:
    """Exceptions raised inside the coroutine surface unchanged."""

    with pytest.raises(RuntimeError, match="kaboom"):
        run(_boom())


def test_run_times_out_and_cancels() -> None:
    """A bounded timeout raises instead of hanging forever."""

    with pytest.raises(concurrent.futures.TimeoutError):
        run(_hang(), timeout=0.05)


def test_run_reuses_one_loop() -> None:
    """Sequential calls share the same background loop."""

    async def _loop_id() -> int:  # noqa: RUF029 - coroutine required by run()'s API
        return id(asyncio.get_running_loop())

    assert run(_loop_id()) == run(_loop_id())


def test_run_works_when_caller_has_a_running_loop() -> None:
    """The bridge works from inside an already-running event loop.

    This is the whole point of the bridge: a naive asyncio.run() in the
    sync surface would raise 'asyncio.run() cannot be called from a
    running event loop' in notebooks/agent runtimes.
    """

    async def _call_sync_api_from_async_context() -> int:  # noqa: RUF029
        return run(_double(5))

    assert asyncio.run(_call_sync_api_from_async_context()) == 10  # noqa: PLR2004
