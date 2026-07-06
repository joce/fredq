"""Tests for tools/check_no_skips.py's skip-detection logic.

Exercises the collector plugin and main()'s decision logic directly against
synthetic pytest.TestReport objects and a monkeypatched pytest.main — no
subprocess, no real pytest collection/run, no network.
"""

from __future__ import annotations

import pytest

from tools.check_no_skips import (
    _SkipCollector,  # pyright: ignore[reportPrivateUsage]
    main,
)


def _report(
    nodeid: str,
    outcome: str = "passed",
    *,
    wasxfail: str | None = None,
) -> pytest.TestReport:
    """Build a real pytest.TestReport for a single test phase.

    Args:
        nodeid: The test node ID to record on the report.
        outcome: One of "passed", "failed", "skipped".
        wasxfail: When given, sets the ``wasxfail`` extra attribute pytest
            attaches to skip reports produced by an ``xfail`` outcome.

    Returns:
        pytest.TestReport: A real report instance, not a stub.
    """

    report = pytest.TestReport(
        nodeid=nodeid,
        location=(nodeid, None, nodeid),
        keywords={},
        outcome=outcome,  # type: ignore[arg-type]
        longrepr=None,
        when="call",
    )
    if wasxfail is not None:
        report.wasxfail = wasxfail
    return report


def test_collector_ignores_passed_reports() -> None:
    """A passing report is not recorded as a skip."""

    collector = _SkipCollector()
    collector.pytest_runtest_logreport(_report("tests/test_x.py::test_ok"))
    assert collector.skipped == []


def test_collector_records_genuine_skip() -> None:
    """A skipped report with no wasxfail flag is recorded by node ID."""

    collector = _SkipCollector()
    collector.pytest_runtest_logreport(
        _report("tests/test_x.py::test_skipped", outcome="skipped")
    )
    assert collector.skipped == ["tests/test_x.py::test_skipped"]


def test_collector_ignores_xfail_flagged_skip() -> None:
    """Xfail outcomes report as skipped but carry wasxfail; not counted."""

    collector = _SkipCollector()
    collector.pytest_runtest_logreport(
        _report("tests/test_x.py::test_xfail", outcome="skipped", wasxfail="known bug")
    )
    assert collector.skipped == []


def test_collector_accumulates_multiple_skips_in_order() -> None:
    """Multiple skipped tests are all recorded, in report order."""

    collector = _SkipCollector()
    collector.pytest_runtest_logreport(
        _report("tests/test_x.py::test_a", outcome="skipped")
    )
    collector.pytest_runtest_logreport(_report("tests/test_x.py::test_b"))
    collector.pytest_runtest_logreport(
        _report("tests/test_x.py::test_c", outcome="skipped")
    )
    assert collector.skipped == [
        "tests/test_x.py::test_a",
        "tests/test_x.py::test_c",
    ]


def test_main_zero_skips_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """When pytest reports no skips, main() returns pytest's exit code."""

    def fake_pytest_main(*_args: object, **_kwargs: object) -> int:
        return 0

    monkeypatch.setattr("tools.check_no_skips.pytest.main", fake_pytest_main)
    assert main() == 0


def test_main_unexpected_skip_fails_naming_the_test(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A single unexpected skip fails the check and names the node ID."""

    def fake_pytest_main(_args: object, plugins: list[_SkipCollector]) -> int:
        plugins[0].skipped.append("tests/test_frames.py::test_to_pandas")
        return 0

    monkeypatch.setattr("tools.check_no_skips.pytest.main", fake_pytest_main)
    assert main() == 1
    captured = capsys.readouterr()
    assert "tests/test_frames.py::test_to_pandas" in captured.err
    assert "1 test(s) skipped" in captured.err


def test_main_multiple_unexpected_skips_all_named(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every skipped node ID is listed in the failure output."""

    def fake_pytest_main(_args: object, plugins: list[_SkipCollector]) -> int:
        plugins[0].skipped.extend(
            ["tests/test_a.py::test_1", "tests/test_b.py::test_2"]
        )
        return 0

    monkeypatch.setattr("tools.check_no_skips.pytest.main", fake_pytest_main)
    assert main() == 1
    captured = capsys.readouterr()
    assert "tests/test_a.py::test_1" in captured.err
    assert "tests/test_b.py::test_2" in captured.err
    assert "2 test(s) skipped" in captured.err


def test_main_pytest_failure_without_skips_propagates_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real test failure (no skips) surfaces pytest's own exit code."""

    def fake_pytest_main(*_args: object, **_kwargs: object) -> int:
        return 1

    monkeypatch.setattr("tools.check_no_skips.pytest.main", fake_pytest_main)
    assert main() == 1
