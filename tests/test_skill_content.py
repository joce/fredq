"""Integrity gates for the agent-skill content tree (Task 1: content + gates).

Two families of tests live here:

1. **Structural gates** (frontmatter, tree shape, domain index links,
   relative-link resolution, sharp-edge shape) -- content-integrity checks
   that fail on any regression to the tree this task authored.
2. **Snippet pinning** -- every fenced ``python`` block in the content
   tree is pinned so a future edit cannot silently drift from working
   code. One snippet is a byte-identical mirror of README.md's own
   library-quickstart line; it is asserted verbatim-only. The rest each
   get their own offline, corpus-backed behavioral test using the same
   ``_get_client`` monkeypatch seam ``tests/test_core.py`` establishes.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Final

import pytest

import fredq
import fredq._core as core
from fredq.exceptions import FredApiError, FredRequestError

CONTENT: Final[Path] = (
    Path(__file__).parent.parent / "src" / "fredq" / "skills" / "content"
)
DOMAINS: Final[list[str]] = ["catalog", "dataframes", "observations", "revisions"]
_MAX_DESCRIPTION_LENGTH: Final[int] = 1024

_CORPUS_ROOT: Final[Path] = Path(__file__).parent / "fixtures" / "corpus"
_README: Final[Path] = Path(__file__).parent.parent / "README.md"


def _frontmatter() -> dict[str, str]:
    """Parse SKILL.md's YAML frontmatter into a flat dict.

    Returns:
        dict[str, str]: Frontmatter field name -> value.
    """

    text = (CONTENT / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md must open with YAML frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def test_frontmatter_name_matches_skill_directory_contract() -> None:
    """The standard requires name == installed directory name (fredq)."""

    assert _frontmatter()["name"] == "fredq"


def test_frontmatter_description_within_standard_limit() -> None:
    """The description must be non-empty and within the standard's limit."""

    description = _frontmatter()["description"]
    assert description
    assert len(description) <= _MAX_DESCRIPTION_LENGTH


def test_content_tree_has_exactly_the_spec_files() -> None:
    """One SKILL.md + README/SHARP-EDGES per domain; nothing else."""

    files = sorted(
        p.relative_to(CONTENT).as_posix() for p in CONTENT.rglob("*") if p.is_file()
    )
    expected = sorted(
        ["SKILL.md"]
        + [f"{d}/README.md" for d in DOMAINS]
        + [f"{d}/SHARP-EDGES.md" for d in DOMAINS]
    )
    assert files == expected


def test_every_domain_is_linked_from_skill_md() -> None:
    """Every domain directory has a link from SKILL.md's domain index."""

    body = (CONTENT / "SKILL.md").read_text(encoding="utf-8")
    for domain in DOMAINS:
        assert f"{domain}/README.md" in body, f"SKILL.md must index {domain}"


@pytest.mark.parametrize(
    "md", sorted(CONTENT.rglob("*.md")), ids=lambda p: p.name + "/" + p.parent.name
)
def test_relative_links_resolve(md: Path) -> None:
    """Every relative link in a content markdown file points to a real file."""

    body = md.read_text(encoding="utf-8")
    for target in re.findall(r"\]\((?!https?://|#)([^)]+?)(?:#[^)]*)?\)", body):
        assert (md.parent / target).exists(), f"{md.name}: dead link {target}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_sharp_edges_entries_follow_the_fixed_shape(domain: str) -> None:
    """Every `## ` entry carries a Severity line and an Evidence line."""

    body = (CONTENT / domain / "SHARP-EDGES.md").read_text(encoding="utf-8")
    entries = re.split(r"\n## ", body)[1:]
    assert entries, f"{domain}: SHARP-EDGES.md has no entries"
    for entry in entries:
        title = entry.splitlines()[0]
        assert re.search(r"\*\*Severity:\*\* (high|medium|low)", entry), (
            domain,
            title,
        )
        assert "Evidence:" in entry, (domain, title)


# ---------------------------------------------------------------------------
# Snippet pinning
#
# Every fenced ``python`` block across SKILL.md + the four domains' README
# and SHARP-EDGES files is accounted for below: either as a README-mirror
# verbatim-only assertion, or as its own offline, corpus-backed behavioral
# test. Two commands (``series-search``/``series`` in the catalog
# search-then-info example, ``release``/``release-sources`` in the catalog
# release example) are chained in one snippet, so those two tests use a
# path-keyed fake client instead of a single canned body.
# ---------------------------------------------------------------------------


def _corpus_text(relative_path: str) -> str:
    """Read a corpus fixture body as text.

    Returns:
        str: The raw fixture file contents.
    """

    return (_CORPUS_ROOT / relative_path).read_text(encoding="utf-8")


class _FakeClient:
    """Minimal stand-in for FredClient that returns one canned body always.

    Mirrors ``tests/test_core.py``'s ``_StubClient``: the established seam
    for pinning library-API calls offline against a corpus fixture, reused
    here for the skill content snippets.
    """

    def __init__(self, body: str) -> None:
        """Store the canned response body."""

        self.body = body

    async def get(
        self,
        path: str,
        params: dict[str, object],
        *,
        base_url: str | None = None,
    ) -> str:
        """Return the canned body regardless of the request.

        Returns:
            str: The canned response body.
        """

        del path, params, base_url
        return self.body

    async def aclose(self) -> None:
        """No-op close."""


class _PathFakeClient:
    """Stand-in that answers a different canned body per request path.

    For snippets that chain two different commands in one example (e.g.
    search, then look up the top hit): each command has a distinct
    ``CommandSpec.path``, so a single canned body cannot serve both calls.
    """

    def __init__(self, bodies: dict[str, str]) -> None:
        """Store the path -> canned body mapping."""

        self.bodies = bodies

    async def get(
        self,
        path: str,
        params: dict[str, object],
        *,
        base_url: str | None = None,
    ) -> str:
        """Return the canned body registered for ``path``.

        Returns:
            str: The canned response body for this path.
        """

        del params, base_url
        return self.bodies[path]

    async def aclose(self) -> None:
        """No-op close."""


class _ErrorFakeClient:
    """Stand-in whose ``get()`` raises, mirroring a real FRED HTTP rejection."""

    def __init__(self, status_code: int, body: str) -> None:
        """Store the canned error status and body."""

        self.status_code = status_code
        self.body = body

    async def get(
        self,
        path: str,
        params: dict[str, object],
        *,
        base_url: str | None = None,
    ) -> str:
        """Raise a FredRequestError carrying the canned error body.

        Raises:
            FredRequestError: Always -- the fixture is a real FRED 4xx
                capture, so the caller's error-handling path is what's
                under test, not a successful response.
        """

        del params, base_url
        message_url = f"https://api.stlouisfed.org{path}"
        raise FredRequestError(self.status_code, message_url, body=self.body)

    async def aclose(self) -> None:
        """No-op close."""


def _install_fake(monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    """Patch the core client seam with a fake returning ``body`` for every call."""

    monkeypatch.setattr(core, "_get_client", lambda: _FakeClient(body))


def _install_path_fake(monkeypatch: pytest.MonkeyPatch, bodies: dict[str, str]) -> None:
    """Patch the core client seam with a per-path fake."""

    monkeypatch.setattr(core, "_get_client", lambda: _PathFakeClient(bodies))


def _install_error_fake(
    monkeypatch: pytest.MonkeyPatch, status_code: int, body: str
) -> None:
    """Patch the core client seam with a fake that raises an HTTP error."""

    monkeypatch.setattr(
        core, "_get_client", lambda: _ErrorFakeClient(status_code, body)
    )


def _assert_in_content(domain: str | None, filename: str, snippet: str) -> None:
    """Assert ``snippet`` appears verbatim in a content file."""

    path = CONTENT / domain / filename if domain else CONTENT / filename
    body = path.read_text(encoding="utf-8")
    assert snippet in body, f"{path}: expected snippet not found verbatim"


# --- SKILL.md (2) ------------------------------------------------------


def test_skill_md_quickstart_snippet_mirrors_readme() -> None:
    """SKILL.md's quickstart line is a byte-identical mirror of README.md's.

    Verbatim-only: the call itself is exercised behaviorally by every
    other test below that drives ``Series(...).observations()`` against a
    corpus fixture, so only the mirror needs pinning here.
    """

    snippet = 'obs = fredq.Series("DGS10").observations(observation_start="2024-01-01")'
    assert snippet in _README.read_text(encoding="utf-8")
    _assert_in_content(None, "SKILL.md", snippet)


def test_skill_md_two_surfaces_snippet(monkeypatch: pytest.MonkeyPatch) -> None:
    """SKILL.md's two-surfaces example: ``Series(...).observations(units="pch")``."""

    snippet = 'pch = fredq.Series("CPIAUCSL").observations(units="pch")'
    _assert_in_content(None, "SKILL.md", snippet)

    _install_fake(monkeypatch, _corpus_text("series-observations/CPIAUCSL_pch.json"))
    pch = fredq.Series("CPIAUCSL").observations(units="pch")
    assert pch.meta.units == "pch"
    assert pch.to_polars().height == 36  # noqa: PLR2004 - corpus-pinned row count


# --- observations/README.md (4) -----------------------------------------


def test_observations_readme_fetching(monkeypatch: pytest.MonkeyPatch) -> None:
    """observations/README.md: the plain ``Series(...).observations()`` call."""

    snippet = 'obs = fredq.Series("GNPCA").observations()'
    _assert_in_content("observations", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("series-observations/GNPCA.json"))
    obs = fredq.Series("GNPCA").observations()
    assert obs.to_polars().height == 97  # noqa: PLR2004 - corpus-pinned row count


def test_observations_readme_units_transform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """observations/README.md: the ``units="pch"`` transform example."""

    snippet = (
        'pch = fredq.Series("CPIAUCSL").observations(\n'
        '    units="pch", observation_start="2020-01-01", '
        'observation_end="2022-12-31"\n'
        ")"
    )
    _assert_in_content("observations", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("series-observations/CPIAUCSL_pch.json"))
    pch = fredq.Series("CPIAUCSL").observations(
        units="pch", observation_start="2020-01-01", observation_end="2022-12-31"
    )
    assert pch.meta.units == "pch"


def test_observations_readme_frequency_aggregation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """observations/README.md: the ``frequency="m"`` aggregation example."""

    snippet = (
        'monthly = fredq.Series("DGS10").observations(\n'
        '    frequency="m", observation_start="2023-01-01", '
        'observation_end="2024-12-31"\n'
        ")"
    )
    _assert_in_content("observations", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("series-observations/DGS10_freq-m.json"))
    monthly = fredq.Series("DGS10").observations(
        frequency="m", observation_start="2023-01-01", observation_end="2024-12-31"
    )
    assert monthly.to_polars().height == 24  # noqa: PLR2004 - corpus-pinned count


def test_observations_readme_missing_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """observations/README.md: the DEXCAUS holiday-gap example."""

    snippet = (
        'obs = fredq.Series("DEXCAUS").observations(\n'
        '    observation_start="2023-12-20", observation_end="2024-01-05"\n'
        ")"
    )
    _assert_in_content("observations", "README.md", snippet)

    _install_fake(
        monkeypatch, _corpus_text("series-observations/DEXCAUS_holidays.json")
    )
    obs = fredq.Series("DEXCAUS").observations(
        observation_start="2023-12-20", observation_end="2024-01-05"
    )
    assert any(row["value"] is None for row in obs.to_dicts())


# --- revisions/README.md (3) ---------------------------------------------


def test_revisions_readme_vintage_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    """revisions/README.md: ``Series(...).vintage_dates()``."""

    snippet = 'dates = fredq.Series("GNPCA").vintage_dates()'
    _assert_in_content("revisions", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("series-vintagedates/GNPCA.json"))
    dates = fredq.Series("GNPCA").vintage_dates()
    assert dates.count == 188  # noqa: PLR2004 - corpus-pinned
    assert len(dates.vintage_dates) == 188  # noqa: PLR2004 - corpus-pinned


def test_revisions_readme_point_in_time_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """revisions/README.md: the UNRATE 2001-realtime-window example."""

    snippet = (
        'asof = fredq.Series("UNRATE").observations(\n'
        '    realtime_start="2001-01-01",\n'
        '    realtime_end="2001-12-31",\n'
        '    observation_start="2000-01-01",\n'
        '    observation_end="2000-12-31",\n'
        ")"
    )
    _assert_in_content("revisions", "README.md", snippet)

    _install_fake(
        monkeypatch, _corpus_text("series-observations/UNRATE_vintage-2001.json")
    )
    asof = fredq.Series("UNRATE").observations(
        realtime_start="2001-01-01",
        realtime_end="2001-12-31",
        observation_start="2000-01-01",
        observation_end="2000-12-31",
    )
    df = asof.to_polars()
    assert df.height == 14  # noqa: PLR2004 - corpus-pinned row count
    assert (df["date"] == date(2000, 3, 1)).sum() == 2  # noqa: PLR2004 - two vintages


def test_revisions_readme_revision_cadence(monkeypatch: pytest.MonkeyPatch) -> None:
    """revisions/README.md: the GDP quarterly-estimate-rounds example."""

    snippet = (
        'gdp = fredq.Series("GDP").observations(\n'
        '    observation_start="2015-01-01", observation_end="2024-12-31"\n'
        ")"
    )
    _assert_in_content("revisions", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("series-observations/GDP_quarterly.json"))
    gdp = fredq.Series("GDP").observations(
        observation_start="2015-01-01", observation_end="2024-12-31"
    )
    assert gdp.to_polars().height == 40  # noqa: PLR2004 - corpus-pinned row count


# --- catalog/README.md (4) -------------------------------------------------


def test_catalog_readme_search_then_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """catalog/README.md: search, then look up the top hit's info.

    Two different commands (``series-search`` then ``series``), so a
    single canned body cannot serve both -- a path-keyed fake answers
    each. Fixture note: no corpus capture exists for the literal top
    "monetary" hit's own ``series show``; ``series/GNPCA.json`` is a
    structurally identical series-show response used as a stand-in for
    the second call. The claim under test is that the two-step
    search-then-info flow routes both calls and both responses validate,
    not that GNPCA is genuinely the top "monetary" hit.
    """

    snippets = [
        'hits = fredq.search_series("monetary")',
        "series_id = hits.seriess[0].id",
        "info = fredq.Series(series_id).info()",
    ]
    for snippet in snippets:
        _assert_in_content("catalog", "README.md", snippet)

    _install_path_fake(
        monkeypatch,
        {
            "/fred/series/search": _corpus_text("series-search/monetary.json"),
            "/fred/series": _corpus_text("series/GNPCA.json"),
        },
    )
    hits = fredq.search_series("monetary")
    series_id = hits.seriess[0].id
    info = fredq.Series(series_id).info()
    assert series_id
    assert info.title


def test_catalog_readme_category_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    """catalog/README.md: ``Category(0).children()``."""

    snippet = "top_level = fredq.Category(0).children()"
    _assert_in_content("catalog", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("category-children/root.json"))
    top_level = fredq.Category(0).children()
    assert len(top_level.categories) == 8  # noqa: PLR2004 - corpus-pinned


def test_catalog_readme_release_and_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """catalog/README.md: ``Release(53).info()`` then ``Release(53).sources()``.

    Two different commands (``release`` then ``release-sources``); a
    path-keyed fake answers each with its own real capture.
    """

    snippets = [
        "release = fredq.Release(53).info()",
        "sources = fredq.Release(53).sources()",
    ]
    for snippet in snippets:
        _assert_in_content("catalog", "README.md", snippet)

    _install_path_fake(
        monkeypatch,
        {
            "/fred/release": _corpus_text("release/53.json"),
            "/fred/release/sources": _corpus_text("release-sources/53.json"),
        },
    )
    release = fredq.Release(53).info()
    sources = fredq.Release(53).sources()
    assert release.name == "Gross Domestic Product"
    assert sources.sources


def test_catalog_readme_tag_series(monkeypatch: pytest.MonkeyPatch) -> None:
    """catalog/README.md: ``tag_series(["usa", "quarterly"])``."""

    snippet = 'matches = fredq.tag_series(["usa", "quarterly"])'
    _assert_in_content("catalog", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("tags-series/usa-quarterly.json"))
    matches = fredq.tag_series(["usa", "quarterly"])
    assert matches.count == 64576  # noqa: PLR2004 - corpus-pinned


# --- catalog/SHARP-EDGES.md (1) ---------------------------------------------


def test_catalog_sharp_edges_one_error_shape_snippet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """catalog/SHARP-EDGES.md's ``FredApiError`` catch-and-branch example."""

    snippet = (
        "from fredq import FredApiError\n"
        "\n"
        "try:\n"
        "    fredq.Category(999999999).info()\n"
        "except FredApiError as exc:\n"
        "    print(exc.status_code, exc.error_code, exc.error_message)"
    )
    _assert_in_content("catalog", "SHARP-EDGES.md", snippet)

    _install_error_fake(monkeypatch, 400, _corpus_text("category/ERR_invalid-id.json"))
    with pytest.raises(FredApiError) as exc_info:
        fredq.Category(999999999).info()
    assert exc_info.value.status_code == 400  # noqa: PLR2004 - corpus-pinned
    assert exc_info.value.error_code == 400  # noqa: PLR2004 - corpus-pinned
    assert "does not exist" in exc_info.value.error_message


# --- dataframes/README.md (3) -----------------------------------------------


def test_dataframes_readme_conversion_vocabulary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dataframes/README.md: the five ``Frame`` conversion methods.

    ``to_pandas()``/``to_arrow()`` need the optional ``pandas`` extra;
    mirrors ``tests/test_frames.py``'s own try/except-ImportError
    convention (never skip -- the ImportError path IS the behavior under
    test in the base env). ``save_parquet()`` is asserted verbatim only
    here (it writes a file; the call shape is what's documented, not disk
    I/O), matching this module's other file-write-free pinning style.
    """

    for snippet in (
        'obs = fredq.Series("TWEXB").observations()',
        "obs.to_polars()",
        "obs.to_pandas()  # requires: pip install fredq[pandas]",
        "obs.to_arrow()  # requires: pip install fredq[pandas]",
        "obs.to_dicts()",
        'obs.save_parquet("twexb.parquet")',
    ):
        _assert_in_content("dataframes", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("series-observations/TWEXB.json"))
    obs = fredq.Series("TWEXB").observations()
    assert obs.to_polars().height == 1305  # noqa: PLR2004 - corpus-pinned
    assert obs.to_dicts()

    try:
        import pandas  # noqa: F401, ICN001, PLC0415
    except ImportError:
        with pytest.raises(ImportError, match=r"fredq\[pandas\]"):
            obs.to_pandas()
    else:
        assert obs.to_pandas().shape[0] == 1305  # noqa: PLR2004 - corpus-pinned

    try:
        import pyarrow  # noqa: F401, ICN001, PLC0415
    except ImportError:
        with pytest.raises(ImportError, match=r"fredq\[pandas\]"):
            obs.to_arrow()
    else:
        assert obs.to_arrow().num_rows == 1305  # noqa: PLR2004 - corpus-pinned


def test_dataframes_readme_meta_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """dataframes/README.md: the ``.meta`` envelope example."""

    snippets = [
        (
            'obs = fredq.Series("DGS10").observations(\n'
            '    observation_start="2024-01-01", observation_end="2024-12-31"\n'
            ")"
        ),
        "meta = obs.meta",
    ]
    for snippet in snippets:
        _assert_in_content("dataframes", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("series-observations/DGS10_2024.json"))
    obs = fredq.Series("DGS10").observations(
        observation_start="2024-01-01", observation_end="2024-12-31"
    )
    meta = obs.meta
    assert meta.units == "lin"


def test_dataframes_readme_joining_frequencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dataframes/README.md: joining two ``Observations`` frames on ``date``.

    Both calls hit the same command (``series-observations``), so one
    canned body serves both -- the claim under test is that the join call
    succeeds against real polars/date dtypes, not that DGS10 and CPIAUCSL
    genuinely share these exact dates.
    """

    snippets = [
        'ten_year = fredq.Series("DGS10").observations(frequency="m").to_polars()',
        'cpi_pch = fredq.Series("CPIAUCSL").observations(units="pch").to_polars()',
        'combined = ten_year.join(cpi_pch, on="date", how="full", suffix="_cpi")',
    ]
    for snippet in snippets:
        _assert_in_content("dataframes", "README.md", snippet)

    _install_fake(monkeypatch, _corpus_text("series-observations/DGS10_freq-m.json"))
    ten_year = fredq.Series("DGS10").observations(frequency="m").to_polars()
    cpi_pch = fredq.Series("CPIAUCSL").observations(units="pch").to_polars()
    combined = ten_year.join(cpi_pch, on="date", how="full", suffix="_cpi")
    assert combined.height == 24  # noqa: PLR2004 - corpus-pinned row count
