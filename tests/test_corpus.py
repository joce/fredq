"""Gates over the committed FRED capture corpus.

The corpus (tests/fixtures/corpus/) is the only authority for wire
spellings, presence, and types (spec §7). These tests make two guarantees:
no API-key material can land in git, and a manifest "ok" always denotes a
real, parseable capture.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Final

import regex

from fredq.auth import resolve_api_key
from fredq.commands import COMMANDS_BY_NAME
from fredq.exceptions import FredApiKeyMissingError

CORPUS_DIR: Final[Path] = Path(__file__).parent / "fixtures" / "corpus"

# api_key= followed by anything except the [REDACTED] marker is a leak.
_KEY_LEAK_RE: Final[regex.Pattern[str]] = regex.compile(r"api_key=(?!\[REDACTED\])\S")


def _corpus_text_files() -> list[Path]:
    assert CORPUS_DIR.is_dir(), "corpus missing - run `uv run python -m tools.probe`"
    return sorted(p for p in CORPUS_DIR.rglob("*") if p.is_file())


def _manifest() -> dict[str, Any]:
    return json.loads((CORPUS_DIR / "manifest.json").read_text(encoding="utf-8"))


def test_no_api_key_material_in_corpus() -> None:
    """SECRET HYGIENE GATE: no key parameter or literal key, anywhere."""

    real_key = os.environ.get("FRED_API_KEY", "").strip()

    # The env var is the primary lookup, but the local dev key usually
    # resolves from the ~/.fredq/api_key fallback file instead (same path
    # the probe itself uses). Check both so a file-only key can never slip
    # through a corpus commit just because CI has no env var set.
    try:
        resolved_key = resolve_api_key()
    except FredApiKeyMissingError:
        resolved_key = ""

    for path in _corpus_text_files():
        text = path.read_text(encoding="utf-8")
        leak = _KEY_LEAK_RE.search(text)
        assert leak is None, f"api_key material in {path}: {leak.group(0)!r}"
        if real_key:
            assert real_key not in text, f"literal API key found in {path}"
        if resolved_key:
            assert resolved_key not in text, f"literal API key found in {path}"


def test_manifest_entries_match_corpus_files() -> None:
    """Manifest and files agree in both directions; every capture parses."""

    manifest = _manifest()
    entries = {k: v for k, v in manifest.items() if k != "_meta"}
    assert manifest["_meta"]["case_count"] == len(entries)

    files_on_disk = {
        p.relative_to(CORPUS_DIR).as_posix()
        for p in _corpus_text_files()
        if p.name not in {"manifest.json", "README.md"}
    }
    files_in_manifest = {str(e["file"]) for e in entries.values() if "file" in e}
    assert files_in_manifest == files_on_disk

    for key, entry in entries.items():
        if "file" in entry:
            capture = CORPUS_DIR / str(entry["file"])
            json.loads(capture.read_text(encoding="utf-8"))  # must parse
        if entry["status"] == "ok":
            assert "file" in entry, f"ok entry without capture: {key}"


def test_every_command_has_corpus_coverage() -> None:
    """All 35 commands have at least one manifest entry (spec §7 pin)."""

    covered = {key.split("/", 1)[0] for key in _manifest() if key != "_meta"}
    missing = set(COMMANDS_BY_NAME) - covered
    assert not missing, f"commands with no corpus evidence: {sorted(missing)}"


def test_error_family_evidence_exists() -> None:
    """The corpus contains deliberate error captures (spec §6 depends on them)."""

    error_entries = [
        e
        for k, e in _manifest().items()
        if k != "_meta" and e["status"] == "http_error"
    ]
    assert error_entries, "no http_error captures in corpus"
    with_bodies = [e for e in error_entries if "file" in e]
    assert with_bodies, "no http_error capture kept its response body"
