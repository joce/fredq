"""Packaging sanity: sdist/wheel membership must match the intended surface.

Hatchling loses VCS-ignore filtering when ``.git`` is a file rather than a
directory — exactly the layout a git worktree uses. The reference
implementation silently shipped 204 ``node_modules`` files in a wheel built
from a worktree once. These tests build the real artifacts with ``uv build``
and assert membership programmatically so that trap cannot recur silently.

No skip decorators: a slow build (~10s) is an accepted cost, not a reason to
skip. The build fixture's own test-session budget is raised with
``@pytest.mark.timeout(120)`` on every test that consumes it, since the
default suite-wide timeout (10s, see ``pyproject.toml``) is tuned for unit
tests, not a subprocess build.
"""

from __future__ import annotations

import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BUILD_TIMEOUT_SECONDS = 120
_WHEEL_MEMBER_CEILING = 100


@dataclass(frozen=True, slots=True)
class _BuiltDistributions:
    """Paths to the wheel and sdist built once for this test session."""

    wheel_names: frozenset[str]
    sdist_names: frozenset[str]


def _wheel_member_names(wheel_path: Path) -> frozenset[str]:
    """Return every file path stored inside a wheel (a zip archive).

    Returns:
        frozenset[str]: Archive member names (forward-slash separated).
    """

    with zipfile.ZipFile(wheel_path) as archive:
        return frozenset(name for name in archive.namelist() if not name.endswith("/"))


def _sdist_member_names(sdist_path: Path) -> frozenset[str]:
    """Return every file path stored inside an sdist (a gzipped tarball).

    The leading ``<project>-<version>/`` directory component is stripped so
    membership checks read the same as the wheel's package-relative paths.

    Returns:
        frozenset[str]: Archive member names relative to the sdist root.
    """

    with tarfile.open(sdist_path, "r:gz") as archive:
        names: list[str] = []
        for member in archive.getmembers():
            if not member.isfile():
                continue
            _prefix, _sep, rest = member.name.partition("/")
            names.append(rest)
        return frozenset(names)


@pytest.fixture(scope="module")
def built_distributions(
    tmp_path_factory: pytest.TempPathFactory,
) -> _BuiltDistributions:
    """Build sdist+wheel once per test module via ``uv build``.

    Returns:
        _BuiltDistributions: Member-name sets for the built wheel and sdist.
    """

    out_dir = tmp_path_factory.mktemp("fredq-dist")
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        # ruff: ignore[start-process-with-partial-path]
        ["uv", "build", "--out-dir", str(out_dir)],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=_BUILD_TIMEOUT_SECONDS,
    )

    wheels = sorted(out_dir.glob("*.whl"))
    sdists = sorted(out_dir.glob("*.tar.gz"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    assert len(sdists) == 1, f"expected exactly one sdist, got {sdists}"

    return _BuiltDistributions(
        wheel_names=_wheel_member_names(wheels[0]),
        sdist_names=_sdist_member_names(sdists[0]),
    )


@pytest.mark.timeout(_BUILD_TIMEOUT_SECONDS)
def test_wheel_contains_the_typed_library_surface(
    built_distributions: _BuiltDistributions,
) -> None:
    """The wheel ships py.typed, the models package, api.py, and frames.py."""

    names = built_distributions.wheel_names
    assert "fredq/py.typed" in names
    assert "fredq/models/__init__.py" in names
    assert "fredq/api.py" in names
    assert "fredq/frames.py" in names


@pytest.mark.timeout(_BUILD_TIMEOUT_SECONDS)
def test_wheel_contains_the_agent_skill_content(
    built_distributions: _BuiltDistributions,
) -> None:
    """The wheel ships the agent skill's router, a domain, and the installer."""

    names = built_distributions.wheel_names
    assert "fredq/skills/content/SKILL.md" in names
    assert "fredq/skills/content/observations/README.md" in names
    assert "fredq/skills/_install.py" in names


@pytest.mark.timeout(_BUILD_TIMEOUT_SECONDS)
def test_wheel_contains_a_spot_check_of_model_modules(
    built_distributions: _BuiltDistributions,
) -> None:
    """Spot-check individual model modules, not just the models package."""

    names = built_distributions.wheel_names
    assert "fredq/models/series.py" in names
    assert "fredq/models/releases.py" in names
    assert "fredq/models/_base.py" in names


@pytest.mark.timeout(_BUILD_TIMEOUT_SECONDS)
def test_wheel_excludes_dev_and_test_only_trees(
    built_distributions: _BuiltDistributions,
) -> None:
    """The wheel must never carry tests, docs, node_modules, or output.

    This is the trap this file exists to catch: hatchling loses its
    VCS-ignore-based exclusion when ``.git`` is a file (a git worktree),
    so a wheel built from a worktree can silently balloon with
    ``node_modules`` or other dev-only trees unless membership is pinned.
    """

    names = built_distributions.wheel_names
    assert not any(name.startswith("tests/") for name in names)
    assert not any("node_modules/" in name for name in names)
    assert not any(name.startswith("docs/") for name in names)
    assert not any(name.startswith("output/") for name in names)
    assert not any(".claude/" in name for name in names)


@pytest.mark.timeout(_BUILD_TIMEOUT_SECONDS)
def test_sdist_ships_the_corpus_by_design(
    built_distributions: _BuiltDistributions,
) -> None:
    """The sdist carries the test corpus (used to gate models at build/test time)."""

    names = built_distributions.sdist_names
    assert "tests/fixtures/corpus/manifest.json" in names
    assert "pyproject.toml" in names


@pytest.mark.timeout(_BUILD_TIMEOUT_SECONDS)
def test_sdist_excludes_dev_only_trees(
    built_distributions: _BuiltDistributions,
) -> None:
    """The sdist must never carry node_modules, .claude, or output."""

    names = built_distributions.sdist_names
    assert not any("node_modules/" in name for name in names)
    assert not any(".claude/" in name for name in names)
    assert not any(name.startswith("output/") for name in names)


@pytest.mark.timeout(_BUILD_TIMEOUT_SECONDS)
def test_wheel_member_count_is_sane(
    built_distributions: _BuiltDistributions,
) -> None:
    """A worktree-triggered leak (e.g. node_modules) balloons this count.

    The reference implementation's incident shipped 204 extra files from
    ``node_modules`` alone; a low three-digit ceiling catches a recurrence
    without pinning an exact (and brittle) file count.
    """

    names = built_distributions.wheel_names
    assert len(names) < _WHEEL_MEMBER_CEILING, sorted(names)
