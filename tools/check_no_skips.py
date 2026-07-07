"""Run a pytest file and fail if any test in it was skipped.

Run from the repo root:  uv run python -m tools.check_no_skips <pytest arg>...

Used by the ``pandas`` tox env to guarantee that tests/test_frames.py's
positive to_pandas/to_arrow paths (the ``else`` branches after the
``import pandas``/``import pyarrow`` probes) actually execute rather than
silently skipping because pandas/pyarrow are missing from the environment.
A green run with those tests skipped would be worse than no env at all, so
the check is mechanical rather than eyeballed.

Also wired into the main test job so any unexpected skip anywhere in the
suite fails CI. All CI jobs run on ubuntu-latest, where the three POSIX-only
chmod tests in tests/test_auth.py (``@pytest.mark.skipif(os.name == "nt", ...)``)
never skip, so no allowlist is needed there. Those tests DO skip when run
locally on Windows; this checker is intended for CI (Linux) use, matching
the reference implementation, which also carries no allowlist mechanism.
"""

from __future__ import annotations

import sys

import pytest


class _SkipCollector:
    """Pytest plugin recording the node ID of every skipped test."""

    def __init__(self) -> None:
        self.skipped: list[str] = []

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Record the test's node ID when its report shows a genuine skip.

        pytest represents ``xfail`` outcomes as ``skipped`` too, flagged
        apart only by ``wasxfail`` — those are expected failures, not
        silently-missing coverage, so they don't count.
        """

        if report.skipped and not hasattr(report, "wasxfail"):
            self.skipped.append(report.nodeid)


def main() -> int:
    """Run pytest over argv[1:] and fail if any test was skipped.

    Returns:
        int: The pytest exit code, or 1 if any test skipped.
    """

    collector = _SkipCollector()
    exit_code = pytest.main(sys.argv[1:], plugins=[collector])
    if collector.skipped:
        skipped_list = "\n".join(f"  - {node_id}" for node_id in collector.skipped)
        print(
            f"ERROR: {len(collector.skipped)} test(s) skipped "
            f"(expected all to run):\n{skipped_list}",
            file=sys.stderr,
        )
        return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
