"""Probe every fredq command across a coverage matrix; write the corpus.

Run from the repo root:  uv run python -m tools.probe

Writes raw response bodies to tests/fixtures/corpus/<command>/<case>.json and
a manifest.json describing every case (argv, status, timestamp). Re-running
and diffing the corpus is the FRED schema-drift detector.

SECRET HYGIENE: every request carries api_key in the query string and the
corpus is committed to git. All bodies, details, and manifest text pass
through scrub_secrets() before touching disk; tests/test_corpus.py enforces
the result. Never weaken either side.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import regex

# Single source of truth for API-key redaction: the client's constants.
# Duplicating the pattern here once caused a drift risk a review caught —
# a fix to one copy would silently not propagate to the corpus scrubber.
from fredq.client import (
    _API_KEY_RE,  # pyright: ignore[reportPrivateUsage]
    _API_KEY_REDACTED,  # pyright: ignore[reportPrivateUsage]
)

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CORPUS_DIR: Final[Path] = REPO_ROOT / "tests" / "fixtures" / "corpus"

# FRED allows ~120 requests/minute; 0.6s keeps a full run near 100/min.
# Never reduce this (spec §7).
POLITENESS_DELAY_SECONDS: Final[float] = 0.6

# Deliberately invalid-but-plausible key for the bad-key error capture.
# 32 chars like a real FRED key, obviously fake, committed on purpose.
FAKE_API_KEY: Final[str] = "ffffffffffffffffffffffffffffffff"

_UNSAFE_NAME_RE: Final[regex.Pattern[str]] = regex.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class ProbeCase:
    """One probe: a CLI-shaped invocation whose output lands in the corpus."""

    command: str  # CommandSpec.name == corpus subdirectory
    case: str  # file stem before sanitization
    argv: tuple[str, ...]  # exactly what would follow `fredq ` on a shell


def sanitize(name: str) -> str:
    """Make a case name filesystem-safe on every platform.

    Returns:
        str: The name with unsafe characters replaced by underscores.
    """

    return _UNSAFE_NAME_RE.sub("_", name)


def scrub_secrets(text: str, api_key: str) -> str:
    """Strip API-key material from any text bound for the corpus.

    Removes both ``api_key=<value>`` query fragments and the literal key
    value itself (defense in depth: FRED error bodies or future URL formats
    could echo the key outside a query string).

    Returns:
        str: The text with all key material replaced by ``[REDACTED]``.
    """

    scrubbed = _API_KEY_RE.sub(_API_KEY_REDACTED, text)
    if api_key:
        scrubbed = scrubbed.replace(api_key, "[REDACTED]")
    return scrubbed
