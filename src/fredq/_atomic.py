"""Failure-safe replacement of exported files."""

from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def atomic_output(path: Path | str) -> Generator[Path]:
    """Yield a sibling file, replacing the destination only on success.

    Existing permissions survive replacement; new files respect the umask.
    """
    destination = Path(path).resolve()
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
    os.close(descriptor)
    try:
        if destination.exists():
            temporary.chmod(stat.S_IMODE(destination.stat().st_mode))
        yield temporary
        temporary.replace(destination)
    finally:
        if os.name == "nt" and temporary.exists():
            temporary.chmod(0o600)
        temporary.unlink(missing_ok=True)
