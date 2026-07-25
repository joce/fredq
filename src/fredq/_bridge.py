"""Run library coroutines on a dedicated background event loop.

The public sync API is a thin facade over async core functions. Those
coroutines run on one lazily-started daemon thread, which keeps the sync
surface usable inside environments that already run an event loop
(notebooks, agent runtimes) where a naive asyncio.run() would raise.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from typing import Any

_T = TypeVar("_T")

_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop  # ruff: ignore[global-statement] - module-level singleton by design
    with _lock:
        if _loop is not None and not _loop.is_closed():
            return _loop
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=loop.run_forever, name="fredq-bridge", daemon=True
        )
        thread.start()
        _loop = loop
    return loop


def run(coro: Coroutine[Any, Any, _T], *, timeout: float | None = None) -> _T:
    """Execute ``coro`` on the bridge loop and return its result.

    ``timeout=None`` (the default) waits forever. With a bounded
    ``timeout``, the wait cannot hang if the daemon loop thread has
    already died (e.g. during interpreter exit); the coroutine is
    cancelled best-effort before the timeout propagates.

    Returns:
        _T: Whatever the coroutine returns.

    Raises:
        concurrent.futures.TimeoutError: If the result is not available
            within ``timeout`` seconds. (An alias of the builtin
            ``TimeoutError`` on Python 3.11+; a distinct ``Exception``
            subclass on 3.10.)
    """

    future = asyncio.run_coroutine_threadsafe(coro, _ensure_loop())
    try:
        return future.result(timeout)
    except concurrent.futures.TimeoutError:
        future.cancel()
        raise
