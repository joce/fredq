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

import asyncio
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Final

import regex

from fredq.auth import resolve_api_key
from fredq.cli import (
    _collect_params,  # pyright: ignore[reportPrivateUsage]
    _enforce_cross_param_rules,  # pyright: ignore[reportPrivateUsage]
    _FredClientProtocol,  # pyright: ignore[reportPrivateUsage]
    _run_command,  # pyright: ignore[reportPrivateUsage]
    build_parser,
)

# Single source of truth for API-key redaction: the client's constants.
# Duplicating the pattern here once caused a drift risk a review caught —
# a fix to one copy would silently not propagate to the corpus scrubber.
from fredq.client import (
    _API_KEY_RE,  # pyright: ignore[reportPrivateUsage]
    _API_KEY_REDACTED,  # pyright: ignore[reportPrivateUsage]
    FredClient,
)
from fredq.commands import COMMANDS_BY_NAME
from fredq.exceptions import FredqError, FredRequestError

if TYPE_CHECKING:
    import argparse

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


def _days_ago_compact(days: int) -> str:
    """Format a UTC timestamp ``days`` before now in FRED's compact format.

    FRED's ``series updates`` start-time/end-time params use YYYYMMDDHhmm,
    not YYYY-MM-DD. This always emits midnight for the given day.

    Returns:
        str: The timestamp as ``YYYYMMDD0000``.
    """

    when = datetime.now(timezone.utc) - timedelta(days=days)
    return when.strftime("%Y%m%d0000")


def _series_show_cases() -> list[ProbeCase]:
    """`series show` across the id matrix plus one ALFRED realtime window.

    Returns:
        list[ProbeCase]: The series-metadata cases.
    """

    ids = (
        "GNPCA",  # annual
        "GDP",  # quarterly
        "DGS10",  # daily
        "CPIAUCSL",  # monthly
        "UNRATE",  # monthly
        "FEDFUNDS",  # monthly
        "DEXCAUS",  # daily FX
        "MORTGAGE30US",  # weekly
        "TWEXB",  # discontinued 2020
    )
    cases = [ProbeCase("series", sid, ("series", "show", sid)) for sid in ids]
    cases.append(
        ProbeCase(
            "series",
            "UNRATE_realtime-2000",
            (
                "series",
                "show",
                "UNRATE",
                "--realtime-start",
                "2000-01-01",
                "--realtime-end",
                "2000-12-31",
            ),
        )
    )
    return cases


def _observation_cases() -> list[ProbeCase]:
    """`series observations`: frequencies, units transforms, ALFRED, "." gaps.

    Returns:
        list[ProbeCase]: The observation cases.
    """

    def obs(case: str, *argv: str) -> ProbeCase:
        return ProbeCase("series-observations", case, ("series", "observations", *argv))

    return [
        obs(
            "DGS10_2024",
            "DGS10",
            "--observation-start",
            "2024-01-01",
            "--observation-end",
            "2024-12-31",
        ),
        obs("GNPCA", "GNPCA"),  # full annual history, small
        obs(
            "GDP_quarterly",
            "GDP",
            "--observation-start",
            "2015-01-01",
            "--observation-end",
            "2024-12-31",
        ),
        obs("TWEXB", "TWEXB"),  # discontinued: fixed end of data
        obs(
            "DEXCAUS_holidays",
            "DEXCAUS",
            "--observation-start",
            "2023-12-20",
            "--observation-end",
            "2024-01-05",
        ),  # "." missing values
        obs(
            "CPIAUCSL_pch",
            "CPIAUCSL",
            "--units",
            "pch",
            "--observation-start",
            "2020-01-01",
            "--observation-end",
            "2022-12-31",
        ),
        obs("GNPCA_log", "GNPCA", "--units", "log"),
        obs(
            "FEDFUNDS_chg",
            "FEDFUNDS",
            "--units",
            "chg",
            "--observation-start",
            "2022-01-01",
            "--observation-end",
            "2023-12-31",
        ),
        obs(
            "DGS10_freq-m",
            "DGS10",
            "--frequency",
            "m",
            "--observation-start",
            "2023-01-01",
            "--observation-end",
            "2024-12-31",
        ),
        obs(
            "UNRATE_vintage-2001",
            "UNRATE",
            "--realtime-start",
            "2001-01-01",
            "--realtime-end",
            "2001-12-31",
            "--observation-start",
            "2000-01-01",
            "--observation-end",
            "2000-12-31",
        ),  # ALFRED revisions
        obs(
            "DGS10_future-window",
            "DGS10",
            "--observation-start",
            "2030-01-01",
            "--observation-end",
            "2030-12-31",
        ),  # empty-or-error evidence
    ]


def _series_search_cases() -> list[ProbeCase]:
    """The three search commands, pagination, filters, and an empty result.

    Returns:
        list[ProbeCase]: The search-family cases.
    """

    return [
        ProbeCase("series-search", "monetary", ("series", "search", "monetary")),
        ProbeCase(
            "series-search",
            "monetary_page2",
            ("series", "search", "monetary", "--limit", "5", "--offset", "5"),
        ),
        ProbeCase(
            "series-search",
            "unemployment_filter-monthly",
            (
                "series",
                "search",
                "unemployment",
                "--filter-variable",
                "frequency",
                "--filter-value",
                "Monthly",
                "--limit",
                "5",
            ),
        ),
        ProbeCase(
            "series-search",
            "exchange_tags",
            (
                "series",
                "search",
                "exchange rate",
                "--tag-names",
                "usa;daily",
                "--limit",
                "5",
            ),
        ),
        ProbeCase(
            "series-search", "EMPTY_RESULT", ("series", "search", "zzxqqzyxnonsense")
        ),
        ProbeCase(
            "series-search-tags", "monetary", ("series", "search-tags", "monetary")
        ),
        ProbeCase(
            "series-search-tags",
            "monetary_filtered",
            (
                "series",
                "search-tags",
                "monetary",
                "--tag-search-text",
                "quarterly",
                "--limit",
                "10",
            ),
        ),
        ProbeCase(
            "series-search-related-tags",
            "monetary_usa",
            (
                "series",
                "search-related-tags",
                "monetary",
                "--tag-names",
                "usa",
                "--limit",
                "10",
            ),
        ),
    ]


def _series_misc_cases() -> list[ProbeCase]:
    """vintage-dates, categories, tags, release, updates for the series noun.

    Returns:
        list[ProbeCase]: The remaining series-family cases.
    """

    return [
        ProbeCase("series-vintagedates", "GNPCA", ("series", "vintage-dates", "GNPCA")),
        ProbeCase(
            "series-vintagedates",
            "GNPCA_page-desc",
            (
                "series",
                "vintage-dates",
                "GNPCA",
                "--limit",
                "10",
                "--offset",
                "5",
                "--sort-order",
                "desc",
            ),
        ),
        ProbeCase("series-categories", "DGS10", ("series", "categories", "DGS10")),
        ProbeCase("series-categories", "UNRATE", ("series", "categories", "UNRATE")),
        ProbeCase("series-tags", "DGS10", ("series", "tags", "DGS10")),
        ProbeCase(
            "series-tags",
            "GNPCA_by-name",
            ("series", "tags", "GNPCA", "--order-by", "name", "--sort-order", "desc"),
        ),
        ProbeCase("series-release", "DGS10", ("series", "release", "DGS10")),
        ProbeCase("series-release", "GNPCA", ("series", "release", "GNPCA")),
        ProbeCase("series-updates", "default", ("series", "updates")),
        ProbeCase("series-updates", "limit10", ("series", "updates", "--limit", "10")),
        # argv is time-relative by design (updates only exist near "now");
        # its manifest argv drifts on every re-run — corpus diffs must
        # ignore the start/end-time values for this one case.
        ProbeCase(
            "series-updates",
            "RECENT_WINDOW",
            (
                "series",
                "updates",
                "--start-time",
                _days_ago_compact(2),
                "--end-time",
                _days_ago_compact(0),
                "--limit",
                "10",
            ),
        ),
        ProbeCase(
            "series-updates",
            "filter-macro",
            ("series", "updates", "--filter-value", "macro", "--limit", "10"),
        ),
    ]


def _category_cases() -> list[ProbeCase]:
    """Category noun: root/mid/leaf ids, children/related, series/tags.

    Category ids: 0 = root, 32991 = Money/Banking (mid), 125 = Trade
    Balance (deep), 32073 = a category with related categories.

    Returns:
        list[ProbeCase]: The category-family cases.
    """

    return [
        ProbeCase("category", "root", ("category", "show", "0")),
        ProbeCase("category", "32991", ("category", "show", "32991")),
        ProbeCase("category", "125", ("category", "show", "125")),
        ProbeCase("category-children", "root", ("category", "children", "0")),
        ProbeCase("category-children", "32991", ("category", "children", "32991")),
        ProbeCase(
            "category-children", "125_maybe-leaf", ("category", "children", "125")
        ),
        ProbeCase("category-related", "32073", ("category", "related", "32073")),
        ProbeCase(
            "category-related", "125_maybe-empty", ("category", "related", "125")
        ),
        ProbeCase("category-series", "125", ("category", "series", "125")),
        ProbeCase(
            "category-series",
            "125_page-desc",
            (
                "category",
                "series",
                "125",
                "--limit",
                "3",
                "--offset",
                "3",
                "--sort-order",
                "desc",
            ),
        ),
        ProbeCase(
            "category-series",
            "32991_filter-monthly",
            (
                "category",
                "series",
                "32991",
                "--filter-variable",
                "frequency",
                "--filter-value",
                "Monthly",
                "--limit",
                "5",
            ),
        ),
        ProbeCase("category-tags", "125", ("category", "tags", "125")),
        ProbeCase(
            "category-tags",
            "125_group-gen",
            ("category", "tags", "125", "--tag-group-id", "gen", "--limit", "10"),
        ),
        ProbeCase(
            "category-related-tags",
            "125_services-quarterly",
            (
                "category",
                "related-tags",
                "125",
                "--tag-names",
                "services;quarterly",
                "--limit",
                "10",
            ),
        ),
    ]


def _release_cases() -> list[ProbeCase]:
    """Release noun: catalog, calendar, entity lookups, tables.

    Release ids: 53 = GDP (has tables), 10 = CPI, 175 = Employment Cost.

    Returns:
        list[ProbeCase]: The release-family cases.
    """

    return [
        ProbeCase("releases", "default", ("release", "list")),
        ProbeCase(
            "releases",
            "page-desc",
            (
                "release",
                "list",
                "--limit",
                "5",
                "--offset",
                "2",
                "--sort-order",
                "desc",
            ),
        ),
        ProbeCase(
            "releases-dates", "limit50", ("release", "calendar", "--limit", "50")
        ),
        ProbeCase(
            "releases-dates",
            "nodata",
            (
                "release",
                "calendar",
                "--include-release-dates-with-no-data",
                "--limit",
                "20",
            ),
        ),
        ProbeCase("release", "53", ("release", "show", "53")),
        ProbeCase("release", "10", ("release", "show", "10")),
        ProbeCase(
            "release-dates",
            "53_desc",
            ("release", "dates", "53", "--limit", "10", "--sort-order", "desc"),
        ),
        ProbeCase(
            "release-dates",
            "53_nodata",
            (
                "release",
                "dates",
                "53",
                "--include-release-dates-with-no-data",
                "--limit",
                "10",
            ),
        ),
        ProbeCase("release-series", "53", ("release", "series", "53", "--limit", "5")),
        ProbeCase(
            "release-series",
            "10_filter-monthly",
            (
                "release",
                "series",
                "10",
                "--filter-variable",
                "frequency",
                "--filter-value",
                "Monthly",
                "--limit",
                "5",
            ),
        ),
        ProbeCase("release-sources", "53", ("release", "sources", "53")),
        ProbeCase("release-sources", "10", ("release", "sources", "10")),
        ProbeCase("release-tags", "53", ("release", "tags", "53", "--limit", "10")),
        ProbeCase(
            "release-related-tags",
            "53_usa",
            ("release", "related-tags", "53", "--tag-names", "usa", "--limit", "10"),
        ),
        ProbeCase("release-tables", "53", ("release", "tables", "53")),
        ProbeCase(
            "release-tables",
            "53_with-values",
            (
                "release",
                "tables",
                "53",
                "--include-observation-values",
                "--observation-date",
                "2023-01-01",
            ),
        ),
        ProbeCase(
            "release-tables", "175_maybe-no-tables", ("release", "tables", "175")
        ),  # with/without-tables axis
    ]


def _source_cases() -> list[ProbeCase]:
    """Source noun: catalog + entity + releases (ids 1 = Board, 3 = BLS).

    Returns:
        list[ProbeCase]: The source-family cases.
    """

    return [
        ProbeCase("sources", "default", ("source", "list")),
        ProbeCase("sources", "limit5", ("source", "list", "--limit", "5")),
        ProbeCase("source", "1", ("source", "show", "1")),
        ProbeCase("source", "3", ("source", "show", "3")),
        ProbeCase("source-releases", "1", ("source", "releases", "1")),
        ProbeCase(
            "source-releases",
            "1_page-desc",
            ("source", "releases", "1", "--limit", "5", "--sort-order", "desc"),
        ),
    ]


def _tag_cases() -> list[ProbeCase]:
    """Tag noun: catalog with group/search/pagination, series, related.

    Returns:
        list[ProbeCase]: The tag-family cases.
    """

    return [
        ProbeCase("tags", "default", ("tag", "list")),
        ProbeCase("tags", "group-freq", ("tag", "list", "--tag-group-id", "freq")),
        ProbeCase(
            "tags",
            "search-quarterly",
            ("tag", "list", "--search-text", "quarterly", "--limit", "20"),
        ),
        ProbeCase(
            "tags",
            "page-by-name",
            (
                "tag",
                "list",
                "--limit",
                "10",
                "--offset",
                "5",
                "--order-by",
                "name",
                "--sort-order",
                "desc",
            ),
        ),
        ProbeCase(
            "tags-series",
            "usa-quarterly",
            ("tag", "series", "usa;quarterly", "--limit", "10"),
        ),
        ProbeCase(
            "tags-series",
            "usa_exclude-nsa",
            ("tag", "series", "usa", "--exclude-tag-names", "nsa", "--limit", "10"),
        ),
        ProbeCase("related-tags", "usa", ("tag", "related", "usa", "--limit", "10")),
        ProbeCase(
            "related-tags",
            "monetary_group-geo",
            ("tag", "related", "monetary", "--tag-group-id", "geo", "--limit", "10"),
        ),
    ]


def _geofred_cases() -> list[ProbeCase]:
    """GeoFRED: series group/data, regional snapshot, two shape files.

    The shapes command requires --out; the probe captures the body directly
    and never writes that file, so the path is a stable dummy under the
    gitignored output/ directory.

    Returns:
        list[ProbeCase]: The geofred-family cases.
    """

    return [
        ProbeCase("series-group", "WIPCPI", ("geofred", "series-group", "WIPCPI")),
        ProbeCase("series-data", "WIPCPI", ("geofred", "series-data", "WIPCPI")),
        ProbeCase(
            "series-data",
            "WIPCPI_2020",
            ("geofred", "series-data", "WIPCPI", "--start-date", "2020-01-01"),
        ),
        ProbeCase(
            "series-data",
            "WIPCPI_single-date",
            ("geofred", "series-data", "WIPCPI", "--date", "2023-01-01"),
        ),
        ProbeCase(
            "regional-data",
            "882_state-2020",
            (
                "geofred",
                "regional-data",
                "882",
                "--region-type",
                "state",
                "--date",
                "2020-01-01",
                "--season",
                "NSA",
                "--frequency",
                "a",
                "--units",
                "Dollars",
            ),
        ),
        ProbeCase(
            "regional-data",
            "882_agg-avg",
            (
                "geofred",
                "regional-data",
                "882",
                "--region-type",
                "state",
                "--date",
                "2020-01-01",
                "--season",
                "NSA",
                "--frequency",
                "a",
                "--units",
                "Dollars",
                "--start-date",
                "2019-01-01",
                "--aggregation-method",
                "avg",
            ),
        ),
        ProbeCase(
            "shapes",
            "frb",
            ("geofred", "shapes", "frb", "--out", "output/probe-shape-frb.geojson"),
        ),
        ProbeCase(
            "shapes",
            "state",
            ("geofred", "shapes", "state", "--out", "output/probe-shape-state.geojson"),
        ),
    ]


def _error_cases() -> list[ProbeCase]:
    """Deliberate failures: every error-payload family, one bad API key.

    Returns:
        list[ProbeCase]: The error-capture cases.
    """

    return [
        ProbeCase("series", "ERR_invalid-id", ("series", "show", "ZZZNOTREAL")),
        ProbeCase(
            "series-observations",
            "ERR_invalid-id",
            ("series", "observations", "ZZZNOTREAL"),
        ),
        ProbeCase(
            "series-vintagedates",
            "ERR_invalid-id",
            ("series", "vintage-dates", "ZZZNOTREAL"),
        ),
        ProbeCase("category", "ERR_invalid-id", ("category", "show", "999999999")),
        ProbeCase("release", "ERR_invalid-id", ("release", "show", "999999")),
        ProbeCase("source", "ERR_invalid-id", ("source", "show", "999999")),
        ProbeCase("tags-series", "ERR_bogus-tag", ("tag", "series", "zzqqxbogustag")),
        ProbeCase(
            "series-group", "ERR_invalid-id", ("geofred", "series-group", "ZZZNOTREAL")
        ),
        ProbeCase(
            "regional-data",
            "ERR_invalid-group",
            (
                "geofred",
                "regional-data",
                "999999",
                "--region-type",
                "state",
                "--date",
                "2020-01-01",
                "--season",
                "NSA",
                "--frequency",
                "a",
                "--units",
                "Dollars",
            ),
        ),
        ProbeCase(
            "series",
            "ERR_bad-api-key",
            ("--api-key", FAKE_API_KEY, "series", "show", "GNPCA"),
        ),
    ]


def build_cases() -> list[ProbeCase]:
    """Full declarative probe plan.

    Returns:
        list[ProbeCase]: Every case, in execution order.
    """

    return (
        _series_show_cases()
        + _observation_cases()
        + _series_search_cases()
        + _series_misc_cases()
        + _category_cases()
        + _release_cases()
        + _source_cases()
        + _tag_cases()
        + _geofred_cases()
        + _error_cases()
    )


ClientFactory = Callable[[str], "_FredClientProtocol"]


def _default_client_factory(api_key: str) -> _FredClientProtocol:
    """Build the real FRED client for one probe case.

    Returns:
        _FredClientProtocol: A fresh client bound to ``api_key``.
    """

    return FredClient(api_key)


def _raise_rule_error(message: str) -> None:
    """Raise a ``ValueError`` for a cross-param rule violation.

    Extracted so the ``try`` block in :func:`_execute_case` only ever calls
    out to functions, never raises directly (TRY301).

    Raises:
        ValueError: Always; ``message`` becomes the error text.
    """

    raise ValueError(message)


async def _execute_case(
    parser: argparse.ArgumentParser,
    case: ProbeCase,
    api_key: str,
    client_factory: ClientFactory,
) -> str:
    """Parse, validate, and run one case through the CLI pipeline.

    Propagates ``ValueError`` (argument coercion or a cross-param rule
    failure), ``FredRequestError``, or any other ``FredqError`` to the
    caller, which records them as manifest entries instead of crashing.

    Returns:
        str: The response body (empty string if never reached).
    """

    namespace = parser.parse_args(list(case.argv))
    command = COMMANDS_BY_NAME[namespace.command_name]
    params = _collect_params(command, namespace)
    rule_error = _enforce_cross_param_rules(command, params)
    if rule_error is not None:
        _raise_rule_error(rule_error)
    case_key = namespace.api_key or api_key
    return await _run_command(client_factory(case_key), command, params)


async def _run_case(
    parser: argparse.ArgumentParser,
    case: ProbeCase,
    corpus_dir: Path,
    api_key: str,
    client_factory: ClientFactory,
) -> dict[str, object]:
    """Execute one case through the CLI parsing pipeline; write its body.

    Returns:
        dict[str, object]: The manifest entry for this case.
    """

    entry: dict[str, object] = {
        "argv": list(case.argv),
        "status": "ok",
        "http_status": 200,
    }
    body = ""
    try:
        body = await _execute_case(parser, case, api_key, client_factory)
    except FredRequestError as exc:
        entry["status"] = "http_error"
        entry["http_status"] = exc.status_code
        entry["detail"] = scrub_secrets(str(exc), api_key)
        body = exc.body or ""
    except (FredqError, ValueError) as exc:
        # ValueError covers param coercion and cross-param rule violations;
        # a typo'd probe case becomes a manifest entry, not a crash.
        entry["status"] = "error"
        entry["http_status"] = None
        entry["detail"] = scrub_secrets(str(exc), api_key)
    if body and entry["status"] == "ok":
        try:
            json.loads(body)
        except ValueError as exc:
            # An HTTP-200 body that does not parse as JSON is corruption:
            # record it as an error with NO corpus file, so a manifest "ok"
            # always means the capture parses (spec §7; yoghurt trap).
            entry["status"] = "error"
            entry["detail"] = f"response is not valid JSON: {exc}"
            return entry
    if body:
        relative = f"{case.command}/{sanitize(case.case)}.json"
        target = corpus_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # write_bytes: no newline translation (CRLF trap), byte-exact bodies.
        target.write_bytes(scrub_secrets(body, api_key).encode("utf-8"))
        entry["file"] = relative
    return entry


def _write_manifest(
    manifest: dict[str, object], case_count: int, corpus_dir: Path
) -> None:
    """Attach run metadata and write manifest.json to the corpus dir."""

    manifest["_meta"] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "case_count": case_count,
    }
    corpus_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    with (corpus_dir / "manifest.json").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(text)


async def run_probe(
    cases: list[ProbeCase],
    corpus_dir: Path,
    *,
    api_key: str,
    client_factory: ClientFactory = _default_client_factory,
    delay_seconds: float = 0.0,
) -> None:
    """Run every case sequentially; write the corpus plus manifest.json.

    The manifest is written in a ``finally`` block so hours of politely
    rate-limited evidence survive a crash on a late case.
    """

    parser = build_parser()
    manifest: dict[str, object] = {}
    try:
        for index, case in enumerate(cases, start=1):
            key = f"{case.command}/{case.case}"
            print(f"[{index}/{len(cases)}] {key}", file=sys.stderr)
            manifest[key] = await _run_case(
                parser, case, corpus_dir, api_key, client_factory
            )
            if delay_seconds:
                await asyncio.sleep(delay_seconds)
    finally:
        _write_manifest(manifest, len(manifest), corpus_dir)


def main() -> int:
    """Run the full probe against live FRED.

    Returns:
        int: Process exit code.
    """

    api_key = resolve_api_key()
    asyncio.run(
        run_probe(
            build_cases(),
            CORPUS_DIR,
            api_key=api_key,
            delay_seconds=POLITENESS_DELAY_SECONDS,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
