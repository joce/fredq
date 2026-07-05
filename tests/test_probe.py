"""Tests for the probe harness (sanitizer, case matrix, runner)."""

from __future__ import annotations

import pytest

from fredq.cli import build_parser
from fredq.commands import COMMANDS_BY_NAME
from tools.probe import (
    FAKE_API_KEY,
    POLITENESS_DELAY_SECONDS,
    build_cases,
    sanitize,
    scrub_secrets,
)


def test_sanitize_makes_names_filesystem_safe() -> None:
    """Case names with URL/query characters become portable file stems."""

    assert sanitize("usa;quarterly") == "usa_quarterly"
    assert sanitize("DGS10_freq-m") == "DGS10_freq-m"
    assert sanitize("a b/c\\d:e") == "a_b_c_d_e"


def test_scrub_secrets_redacts_api_key_params() -> None:
    """Any api_key=... query fragment is replaced, wherever it appears."""

    expected_redaction_count = 2
    text = 'GET https://x/fred/series?api_key=abc123&file_type=json "api_key=zzz"'
    scrubbed = scrub_secrets(text, api_key="")
    assert "abc123" not in scrubbed
    assert "zzz" not in scrubbed
    assert scrubbed.count("api_key=[REDACTED]") == expected_redaction_count


def test_scrub_secrets_redacts_literal_key() -> None:
    """The literal key value is removed even outside api_key= fragments."""

    scrubbed = scrub_secrets(
        "the key hush-hush-32chars leaked", api_key="hush-hush-32chars"
    )
    assert "hush-hush-32chars" not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_scrub_secrets_empty_key_is_safe() -> None:
    """An empty key must not cause replace-everything behavior."""

    assert scrub_secrets("plain text", api_key="") == "plain text"


def test_scrub_secrets_is_idempotent() -> None:
    """Re-scrubbing already-scrubbed text is a no-op.

    The manifest and re-run diffs may pass through the scrubber twice; a
    pattern that re-matched ``[REDACTED]`` would corrupt committed text.
    """

    text = "https://x/fred/series?api_key=abc123&file_type=json plus key9"
    once = scrub_secrets(text, api_key="key9")
    assert scrub_secrets(once, api_key="key9") == once


def test_scrub_secrets_redacts_key_at_end_of_string() -> None:
    """A key with no trailing delimiter (end of URL) is still scrubbed."""

    scrubbed = scrub_secrets("https://x/fred/series?api_key=abc123", api_key="")
    assert scrubbed == "https://x/fred/series?api_key=[REDACTED]"


def test_every_case_targets_a_real_command() -> None:
    """Each case's command is a routing key in COMMANDS_BY_NAME."""

    for case in build_cases():
        assert case.command in COMMANDS_BY_NAME, case.case


def test_case_keys_are_unique() -> None:
    """command/case pairs are unique (they become corpus file paths)."""

    keys = [f"{c.command}/{c.case}" for c in build_cases()]
    assert len(keys) == len(set(keys))


def test_every_command_is_covered() -> None:
    """All 35 CommandSpecs appear in the probe plan at least once."""

    covered = {c.command for c in build_cases()}
    missing = set(COMMANDS_BY_NAME) - covered
    assert not missing, f"commands never probed: {sorted(missing)}"


def test_every_argv_parses_and_routes_to_its_command() -> None:
    """Every argv parses via the real CLI parser and routes as labeled.

    A typo'd case must die here, in tests, not against live FRED.
    """

    parser = build_parser()
    for case in build_cases():
        try:
            namespace = parser.parse_args(list(case.argv))
        except SystemExit:  # argparse exits on bad argv
            pytest.fail(f"argv failed to parse: {case.command}/{case.case}")
        assert namespace.command_name == case.command, case.case


def test_politeness_delay_is_never_shrunk() -> None:
    """FRED allows ~120 req/min; the spec pins the floor at 0.5s."""

    floor_seconds = 0.5
    assert floor_seconds <= POLITENESS_DELAY_SECONDS


def test_fake_api_key_is_obviously_fake() -> None:
    """The committed bad-key probe value can never be a real key."""

    assert FAKE_API_KEY == "f" * 32
