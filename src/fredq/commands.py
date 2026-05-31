"""FRED command metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from fredq.client import FRED_BASE_URL
from fredq.params import ParamKind, ParamSpec, bounds_suffix

# Single source of truth for frequency allowed values.
# Base frequencies accepted by FRED's series/observations endpoint.
_FREQUENCY_BASE: Final[tuple[str, ...]] = ("d", "w", "bw", "m", "q", "sa", "a")
# End-of-period variants are the base codes with a "-e" suffix.
_FREQUENCY_END_OF_PERIOD: Final[tuple[str, ...]] = tuple(
    f"{b}-e" for b in _FREQUENCY_BASE
)
# Smooth-seasonal variants (only monthly and quarterly).
_FREQUENCY_SMOOTH_SEASONAL: Final[tuple[str, ...]] = ("m-ss", "q-ss")

_FREQUENCY_VALUES: Final[tuple[str, ...]] = (
    _FREQUENCY_BASE + _FREQUENCY_END_OF_PERIOD + _FREQUENCY_SMOOTH_SEASONAL
)

_FREQUENCY_HELP: Final[str] = (
    f"Aggregation frequency: {', '.join(_FREQUENCY_BASE)} "
    f"(plus -e variants for end-of-period, "
    f"and -ss for m, q smooth-seasonal)."
)


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Describe one fredq command backed by a FRED API endpoint."""

    name: str
    path: str
    summary: str
    description: str
    params: tuple[ParamSpec, ...]
    examples: tuple[str, ...]
    notes: tuple[str, ...] = ()
    mutually_dependent_params: tuple[frozenset[str], ...] = ()
    at_least_one_of: tuple[frozenset[str], ...] = ()
    requires_partner: tuple[tuple[str, str], ...] = ()
    # Non-None: command lives under a nested subcommand group (e.g. "geofred").
    # None (default): top-level flat command — existing behavior unchanged.
    group: str | None = None
    # When True, the CLI registers --out as a required argument and writes the
    # raw response body to that file instead of stdout.
    output_to_file: bool = False

    @property
    def fred_url(self) -> str:
        """Return the full FRED URL for this endpoint."""

        return f"{FRED_BASE_URL}{self.path}"


# ---------------------------------------------------------------------------
# Shared parameter constants — define once, reuse via tuple composition.
# ---------------------------------------------------------------------------

_SERIES_ID_PARAM: Final[ParamSpec] = ParamSpec(
    name="series_id",
    cli_name="series-id",
    kind=ParamKind.STRING,
    help="FRED series identifier (e.g. GNPCA, DGS10, CPIAUCSL).",
    positional=True,
    required=True,
    metavar="ID",
)

_REALTIME_START_PARAM: Final[ParamSpec] = ParamSpec(
    name="realtime_start",
    cli_name="realtime-start",
    kind=ParamKind.DATE,
    help="ALFRED realtime start date (YYYY-MM-DD). Defaults to today.",
    metavar="DATE",
)

_REALTIME_END_PARAM: Final[ParamSpec] = ParamSpec(
    name="realtime_end",
    cli_name="realtime-end",
    kind=ParamKind.DATE,
    help="ALFRED realtime end date (YYYY-MM-DD). Defaults to today.",
    metavar="DATE",
)

_LIMIT_PARAM: Final[ParamSpec] = ParamSpec(
    name="limit",
    cli_name="limit",
    kind=ParamKind.INTEGER,
    help=f"Maximum number of results to return{bounds_suffix(1, 1000)}.",
    metavar="N",
    min_value=1,
    max_value=1000,
)

_OFFSET_PARAM: Final[ParamSpec] = ParamSpec(
    name="offset",
    cli_name="offset",
    kind=ParamKind.INTEGER,
    help=f"Number of results to skip for pagination{bounds_suffix(0, None)}.",
    metavar="N",
    min_value=0,
)

_SORT_ORDER_PARAM: Final[ParamSpec] = ParamSpec(
    name="sort_order",
    cli_name="sort-order",
    kind=ParamKind.STRING,
    help="Result order: asc or desc.",
    allowed_values=("asc", "desc"),
    metavar="ORDER",
)

_TAG_NAMES_PARAM: Final[ParamSpec] = ParamSpec(
    name="tag_names",
    cli_name="tag-names",
    kind=ParamKind.CSV,
    help=(
        "Semicolon-separated list of tag names to filter by "
        "(e.g. 'usa;annual'). Order does not matter."
    ),
    csv_separator=";",
    metavar="TAGS",
)

_EXCLUDE_TAG_NAMES_PARAM: Final[ParamSpec] = ParamSpec(
    name="exclude_tag_names",
    cli_name="exclude-tag-names",
    kind=ParamKind.CSV,
    help="Semicolon-separated list of tag names to exclude.",
    csv_separator=";",
    metavar="TAGS",
)

_TAG_GROUP_ID_PARAM: Final[ParamSpec] = ParamSpec(
    name="tag_group_id",
    cli_name="tag-group-id",
    kind=ParamKind.STRING,
    help=(
        "Filter tags by group: freq (frequency), gen (general), "
        "geo (geography), geot (geography type), rls (release), "
        "seas (seasonal adjustment), src (source)."
    ),
    allowed_values=("freq", "gen", "geo", "geot", "rls", "seas", "src"),
    metavar="GROUP",
)

_TAG_SEARCH_TEXT_PARAM: Final[ParamSpec] = ParamSpec(
    name="tag_search_text",
    cli_name="tag-search-text",
    kind=ParamKind.STRING,
    help="Full-text search string to filter tags by name.",
    metavar="TEXT",
)

_FILTER_VARIABLE_SERIES_PARAM: Final[ParamSpec] = ParamSpec(
    name="filter_variable",
    cli_name="filter-variable",
    kind=ParamKind.STRING,
    help=("Attribute to filter series by: frequency, units, or seasonal_adjustment."),
    allowed_values=("frequency", "units", "seasonal_adjustment"),
    metavar="VAR",
)

_FILTER_VALUE_PARAM: Final[ParamSpec] = ParamSpec(
    name="filter_value",
    cli_name="filter-value",
    kind=ParamKind.STRING,
    # filter_value validation is intentionally deferred to FRED.
    # frequency values are display names ("Annual", "Monthly", etc.) distinct
    # from the frequency code set; units has hundreds of data-driven values;
    # seasonal_adjustment has four stable values but a partial allowlist would
    # be inconsistent. An invalid value receives a FRED 400 immediately.
    help="Value to match against --filter-variable.",
    metavar="VAL",
)


def _order_by_param(allowed: tuple[str, ...]) -> ParamSpec:
    """Build an order_by ParamSpec with endpoint-specific allowed values.

    Returns:
        ParamSpec: Configured order_by parameter spec.
    """

    return ParamSpec(
        name="order_by",
        cli_name="order-by",
        kind=ParamKind.STRING,
        help=f"Field to sort results by: {', '.join(allowed)}.",
        allowed_values=allowed,
        metavar="FIELD",
    )


# ---------------------------------------------------------------------------
# order_by allowed-value sets per endpoint group
# ---------------------------------------------------------------------------

_ORDER_BY_SERIES_SEARCH: Final[tuple[str, ...]] = (
    "search_rank",
    "series_id",
    "title",
    "units",
    "frequency",
    "seasonal_adjustment",
    "realtime_start",
    "realtime_end",
    "last_updated",
    "observation_start",
    "observation_end",
    "popularity",
    "group_popularity",
)

_ORDER_BY_TAG_LIKE: Final[tuple[str, ...]] = (
    "series_count",
    "popularity",
    "created",
    "name",
    "group_id",
)

_ORDER_BY_RELEASES: Final[tuple[str, ...]] = (
    "release_id",
    "name",
    "press_release",
    "realtime_start",
    "realtime_end",
)

_ORDER_BY_RELEASES_DATES: Final[tuple[str, ...]] = (
    "release_date",
    "release_id",
    "release_name",
    "release_last_updated",
    "press_release",
    "realtime_start",
    "realtime_end",
)

_ORDER_BY_RELEASE_SERIES: Final[tuple[str, ...]] = (
    "series_id",
    "title",
    "units",
    "frequency",
    "seasonal_adjustment",
    "realtime_start",
    "realtime_end",
    "last_updated",
    "observation_start",
    "observation_end",
    "popularity",
    "group_popularity",
)

# release-tags / series-tags / category-tags / global tags all use the same set.
# (named _ORDER_BY_TAG_LIKE — canonical; kept as aliases for removed constants)

# category-series shares the same order_by set as release-series.
_ORDER_BY_CATEGORY_SERIES: Final[tuple[str, ...]] = _ORDER_BY_RELEASE_SERIES

# tags-series shares the same order_by set as release-series (minus search_rank).
_ORDER_BY_TAGS_SERIES: Final[tuple[str, ...]] = _ORDER_BY_RELEASE_SERIES

_CATEGORY_ID_PARAM: Final[ParamSpec] = ParamSpec(
    name="category_id",
    cli_name="category-id",
    kind=ParamKind.INTEGER,
    help=(
        "FRED category identifier (e.g. 32991 for Money & Banking)."
        " The root category (ID 0) is the top of the FRED hierarchy."
    ),
    positional=True,
    required=True,
    metavar="ID",
    min_value=0,
)

_ORDER_BY_SOURCES: Final[tuple[str, ...]] = (
    "source_id",
    "name",
    "realtime_start",
    "realtime_end",
)

# source-releases shares the same order_by set as releases.
_ORDER_BY_SOURCE_RELEASES: Final[tuple[str, ...]] = _ORDER_BY_RELEASES

_SOURCE_ID_PARAM: Final[ParamSpec] = ParamSpec(
    name="source_id",
    cli_name="source-id",
    kind=ParamKind.INTEGER,
    help="FRED source identifier (e.g. 1 for Board of Governors, 3 for St. Louis Fed).",
    positional=True,
    required=True,
    metavar="ID",
    min_value=1,
)

_RELEASE_ID_PARAM: Final[ParamSpec] = ParamSpec(
    name="release_id",
    cli_name="release-id",
    kind=ParamKind.INTEGER,
    help="FRED release identifier (e.g. 53 for GDP, 10 for CPI).",
    positional=True,
    required=True,
    metavar="ID",
    min_value=1,
)

_INCLUDE_RELEASE_DATES_WITH_NO_DATA_PARAM: Final[ParamSpec] = ParamSpec(
    name="include_release_dates_with_no_data",
    cli_name="include-release-dates-with-no-data",
    kind=ParamKind.BOOLEAN,
    help="Include release dates that have no data (true/false).",
)

_SEARCH_TEXT_PARAM: Final[ParamSpec] = ParamSpec(
    name="search_text",
    cli_name="search-text",
    kind=ParamKind.STRING,
    help="Full-text search string to filter results by name.",
    metavar="TEXT",
)

_TAG_NAMES_REQUIRED_PARAM: Final[ParamSpec] = ParamSpec(
    name="tag_names",
    cli_name="tag-names",
    kind=ParamKind.CSV,
    help=(
        "Semicolon-separated list of tags already applied "
        "(required). Order does not matter."
    ),
    required=True,
    csv_separator=";",
    metavar="TAGS",
)

_TAG_NAMES_POSITIONAL_PARAM: Final[ParamSpec] = ParamSpec(
    name="tag_names",
    cli_name="tag-names",
    kind=ParamKind.CSV,
    help="Semicolon-separated list of tag names (e.g. 'usa;monthly').",
    positional=True,
    required=True,
    csv_separator=";",
    metavar="TAGS",
)


# v1 starts with two endpoints to prove the pattern; remaining ~29 added
# incrementally. See AGENTS.md "Architecture" + docs/v2-geofred.md.
_CORE_COMMANDS: Final[tuple[CommandSpec, ...]] = (
    CommandSpec(
        name="series",
        path="/fred/series",
        summary="Show metadata for one FRED series.",
        description=(
            "Return the series record: title, units, frequency, seasonal "
            "adjustment, observation range, last-updated timestamp."
        ),
        params=(_SERIES_ID_PARAM, _REALTIME_START_PARAM, _REALTIME_END_PARAM),
        examples=(
            "fredq series GNPCA",
            "fredq series DGS10 --realtime-start 2024-01-01",
        ),
    ),
    CommandSpec(
        name="series-observations",
        path="/fred/series/observations",
        summary="Fetch observations (values) for one FRED series.",
        description=(
            "Return the time series of dated observation values. Supports "
            "the full ALFRED realtime envelope, observation range, frequency "
            "aggregation, and unit transformations exposed by FRED."
        ),
        params=(
            _SERIES_ID_PARAM,
            ParamSpec(
                name="observation_start",
                cli_name="observation-start",
                kind=ParamKind.DATE,
                help=(
                    "Earliest observation date (YYYY-MM-DD). Defaults to the "
                    "FRED series start."
                ),
                metavar="DATE",
            ),
            ParamSpec(
                name="observation_end",
                cli_name="observation-end",
                kind=ParamKind.DATE,
                help=(
                    "Latest observation date (YYYY-MM-DD). Defaults to the "
                    "FRED series end."
                ),
                metavar="DATE",
            ),
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            ParamSpec(
                name="units",
                cli_name="units",
                kind=ParamKind.STRING,
                help=(
                    "Unit transformation: lin, chg, ch1, pch, pc1, pca, cch, cca, log."
                ),
                allowed_values=(
                    "lin",
                    "chg",
                    "ch1",
                    "pch",
                    "pc1",
                    "pca",
                    "cch",
                    "cca",
                    "log",
                ),
                metavar="UNIT",
            ),
            ParamSpec(
                name="frequency",
                cli_name="frequency",
                kind=ParamKind.STRING,
                help=_FREQUENCY_HELP,
                # Ref: FRED series/observations API docs.
                allowed_values=_FREQUENCY_VALUES,
                metavar="FREQ",
            ),
        ),
        examples=(
            "fredq series-observations GNPCA",
            "fredq series-observations CPIAUCSL --units pch --frequency m",
        ),
        notes=(
            (
                "Returns the full FRED envelope including count/offset/limit; "
                "the observations array lives under the 'observations' key."
            ),
        ),
    ),
    CommandSpec(
        name="series-search",
        path="/fred/series/search",
        summary="Search FRED series by keyword.",
        description=(
            "Return series records whose title, notes, or series ID match the "
            "given search text. Supports full-text and series-ID search modes, "
            "result filtering by frequency/units/seasonal adjustment, and "
            "tag filtering."
        ),
        params=(
            ParamSpec(
                name="search_text",
                cli_name="search-text",
                kind=ParamKind.STRING,
                help="Search string to match against series titles and notes.",
                positional=True,
                required=True,
                metavar="TEXT",
            ),
            ParamSpec(
                name="search_type",
                cli_name="search-type",
                kind=ParamKind.STRING,
                help=(
                    "Search mode: full_text (default) matches title/notes; "
                    "series_id matches the series identifier."
                ),
                allowed_values=("full_text", "series_id"),
                metavar="TYPE",
            ),
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_SERIES_SEARCH),
            _SORT_ORDER_PARAM,
            _FILTER_VARIABLE_SERIES_PARAM,
            _FILTER_VALUE_PARAM,
            _TAG_NAMES_PARAM,
            _EXCLUDE_TAG_NAMES_PARAM,
        ),
        examples=(
            'fredq series-search "consumer price index" --limit 5',
            "fredq series-search UNRATE --search-type series_id",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
        mutually_dependent_params=(frozenset({"filter_variable", "filter_value"}),),
        requires_partner=(("exclude_tag_names", "tag_names"),),
    ),
    CommandSpec(
        name="series-search-tags",
        path="/fred/series/search/tags",
        summary="List tags for a series full-text search.",
        description=(
            "Return the tags associated with series matching the given full-text "
            "search string. Useful for discovering tags to use with "
            "series-search-related-tags."
        ),
        params=(
            ParamSpec(
                name="series_search_text",
                cli_name="series-search-text",
                kind=ParamKind.STRING,
                help="Full-text search string used to select the series set.",
                positional=True,
                required=True,
                metavar="TEXT",
            ),
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _TAG_NAMES_PARAM,
            _TAG_GROUP_ID_PARAM,
            _TAG_SEARCH_TEXT_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_TAG_LIKE),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq series-search-tags monetary --limit 5",
            "fredq series-search-tags inflation --tag-group-id geo",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
    ),
    CommandSpec(
        name="series-search-related-tags",
        path="/fred/series/search/related_tags",
        summary="List tags related to a search and existing tag filter.",
        description=(
            "Return tags related to series matching the search text and already "
            "filtered by the given tag names. Use to drill down into a tag "
            "hierarchy when narrowing series searches."
        ),
        params=(
            ParamSpec(
                name="series_search_text",
                cli_name="series-search-text",
                kind=ParamKind.STRING,
                help="Full-text search string used to select the series set.",
                positional=True,
                required=True,
                metavar="TEXT",
            ),
            _TAG_NAMES_REQUIRED_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _TAG_GROUP_ID_PARAM,
            _TAG_SEARCH_TEXT_PARAM,
            _EXCLUDE_TAG_NAMES_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_TAG_LIKE),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq series-search-related-tags monetary --tag-names usa",
            (
                "fredq series-search-related-tags inflation "
                "--tag-names 'usa;annual' --limit 5"
            ),
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
    ),
    CommandSpec(
        name="series-vintagedates",
        path="/fred/series/vintagedates",
        summary="List vintage dates (revision dates) for one FRED series.",
        description=(
            "Return the dates in history when a series was revised or new data "
            "values were released. Pair with "
            "`series-observations --realtime-start <vintage>` for ALFRED "
            "point-in-time analysis."
        ),
        params=(
            _SERIES_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq series-vintagedates GNPCA",
            "fredq series-vintagedates CPIAUCSL --limit 5 --sort-order desc",
        ),
    ),
    CommandSpec(
        name="series-categories",
        path="/fred/series/categories",
        summary="List categories that contain a given series.",
        description=(
            "Return the FRED categories that the specified series belongs to. "
            "Each category record includes its ID, name, and parent ID."
        ),
        params=(
            _SERIES_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
        ),
        examples=(
            "fredq series-categories GNPCA",
            "fredq series-categories CPIAUCSL",
        ),
    ),
    CommandSpec(
        name="series-tags",
        path="/fred/series/tags",
        summary="List tags assigned to a FRED series.",
        description=(
            "Return the tags attached to the specified series. Each tag record "
            "includes name, group ID, notes, creation date, and series count."
        ),
        params=(
            _SERIES_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _order_by_param(_ORDER_BY_TAG_LIKE),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq series-tags GNPCA",
            "fredq series-tags FEDFUNDS --order-by popularity",
        ),
    ),
    CommandSpec(
        name="series-release",
        path="/fred/series/release",
        summary="Show the release that a FRED series belongs to.",
        description=(
            "Return the release record associated with the specified series, "
            "including release ID, name, and press-release flag."
        ),
        params=(
            _SERIES_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
        ),
        examples=(
            "fredq series-release GNPCA",
            "fredq series-release CPIAUCSL",
        ),
    ),
    CommandSpec(
        name="series-updates",
        path="/fred/series/updates",
        summary="List recently updated FRED series.",
        description=(
            "Return series ordered by their last-updated timestamp, newest "
            "first. Supports macro/regional filtering and a time-window filter "
            "for intraday polling."
        ),
        params=(
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            ParamSpec(
                name="filter_value",
                cli_name="filter-value",
                kind=ParamKind.STRING,
                help=(
                    "Limit results to a data domain: macro, regional, or all "
                    "(default: all)."
                ),
                allowed_values=("macro", "regional", "all"),
                metavar="DOMAIN",
            ),
            ParamSpec(
                name="start_time",
                cli_name="start-time",
                kind=ParamKind.STRING,
                help=(
                    "Earliest update time in YYYYMMDDHhmm format "
                    "(e.g. 202401011200). FRED-specific datetime format."
                ),
                metavar="DATETIME",
            ),
            ParamSpec(
                name="end_time",
                cli_name="end-time",
                kind=ParamKind.STRING,
                help=(
                    "Latest update time in YYYYMMDDHhmm format "
                    "(e.g. 202401012359). FRED-specific datetime format."
                ),
                metavar="DATETIME",
            ),
        ),
        examples=(
            "fredq series-updates --limit 10",
            "fredq series-updates --filter-value macro --limit 5",
        ),
        notes=(
            ("start_time and end_time use FRED's YYYYMMDDHhmm format, not YYYY-MM-DD."),
        ),
    ),
    # ------------------------------------------------------------------
    # Group 2 — Category browse (6 endpoints)
    # ------------------------------------------------------------------
    CommandSpec(
        name="category",
        path="/fred/category",
        summary="Show metadata for one FRED category.",
        description=(
            "Return the category record for the given category ID, including "
            "the category name and parent category ID."
        ),
        params=(_CATEGORY_ID_PARAM,),
        examples=(
            "fredq category 0",
            "fredq category 32991",
        ),
        notes=("The root category (ID 0) is the top of the FRED hierarchy.",),
    ),
    CommandSpec(
        name="category-children",
        path="/fred/category/children",
        summary="List child categories of a FRED category.",
        description=(
            "Return the direct child categories of the given category. "
            "Each record includes the child category ID, name, and parent ID."
        ),
        params=(
            _CATEGORY_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
        ),
        examples=(
            "fredq category-children 0",
            "fredq category-children 32991",
        ),
    ),
    CommandSpec(
        name="category-related",
        path="/fred/category/related",
        summary="List categories related to a given FRED category.",
        description=(
            "Return categories that FRED has tagged as related to the specified "
            "category. Related categories are editorially linked, not strictly "
            "hierarchical."
        ),
        params=(
            _CATEGORY_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
        ),
        examples=(
            "fredq category-related 32991",
            "fredq category-related 106",
        ),
    ),
    CommandSpec(
        name="category-series",
        path="/fred/category/series",
        summary="List series belonging to one FRED category.",
        description=(
            "Return the series records published under the specified category. "
            "Supports tag filtering, attribute filtering, and sorting."
        ),
        params=(
            _CATEGORY_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_CATEGORY_SERIES),
            _SORT_ORDER_PARAM,
            _FILTER_VARIABLE_SERIES_PARAM,
            _FILTER_VALUE_PARAM,
            _TAG_NAMES_PARAM,
            _EXCLUDE_TAG_NAMES_PARAM,
        ),
        examples=(
            "fredq category-series 32991 --limit 5",
            "fredq category-series 106 --tag-names 'usa;annual' --limit 10",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
        mutually_dependent_params=(frozenset({"filter_variable", "filter_value"}),),
        requires_partner=(("exclude_tag_names", "tag_names"),),
    ),
    CommandSpec(
        name="category-tags",
        path="/fred/category/tags",
        summary="List tags for series in one FRED category.",
        description=(
            "Return tags associated with series published under the specified "
            "category. Supports group and text filtering."
        ),
        params=(
            _CATEGORY_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _TAG_NAMES_PARAM,
            _TAG_GROUP_ID_PARAM,
            _SEARCH_TEXT_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_TAG_LIKE),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq category-tags 32991 --limit 10",
            "fredq category-tags 106 --tag-group-id geo",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
    ),
    CommandSpec(
        name="category-related-tags",
        path="/fred/category/related_tags",
        summary="List tags related to a category and existing tag filter.",
        description=(
            "Return tags related to series in the specified category that are "
            "also tagged with the given tag names. Use to drill down into a "
            "category tag hierarchy."
        ),
        params=(
            _CATEGORY_ID_PARAM,
            _TAG_NAMES_REQUIRED_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _TAG_GROUP_ID_PARAM,
            _SEARCH_TEXT_PARAM,
            _EXCLUDE_TAG_NAMES_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_TAG_LIKE),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq category-related-tags 32991 --tag-names usa",
            "fredq category-related-tags 32991 --tag-names 'usa;annual' --limit 5",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
    ),
    # ------------------------------------------------------------------
    # Group 3 — Releases / calendar (9 endpoints)
    # ------------------------------------------------------------------
    CommandSpec(
        name="releases",
        path="/fred/releases",
        summary="List all FRED economic data releases.",
        description=(
            "Return the full catalog of FRED releases. Each record includes "
            "release ID, name, press-release flag, and links."
        ),
        params=(
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_RELEASES),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq releases --limit 10",
            "fredq releases --order-by name --sort-order asc",
        ),
    ),
    CommandSpec(
        name="releases-dates",
        path="/fred/releases/dates",
        summary="List release dates across all FRED releases.",
        description=(
            "Return publication dates across all releases in the FRED calendar. "
            "Optionally include release dates that have no associated data."
        ),
        params=(
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_RELEASES_DATES),
            _SORT_ORDER_PARAM,
            _INCLUDE_RELEASE_DATES_WITH_NO_DATA_PARAM,
        ),
        examples=(
            "fredq releases-dates --limit 10",
            "fredq releases-dates --include-release-dates-with-no-data",
        ),
        notes=(
            (
                "Default realtime range is broad (calendar year start to "
                "9999-12-31), unlike most endpoints which default to today. "
                "Pass --realtime-start / --realtime-end to narrow."
            ),
        ),
    ),
    CommandSpec(
        name="release",
        path="/fred/release",
        summary="Show metadata for one FRED release.",
        description=(
            "Return the release record for the given release ID, including "
            "name, press-release flag, and associated links."
        ),
        params=(
            _RELEASE_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
        ),
        examples=(
            "fredq release 53",
            "fredq release 10",
        ),
    ),
    CommandSpec(
        name="release-dates",
        path="/fred/release/dates",
        summary="List publication dates for one FRED release.",
        description=(
            "Return the dated publication records for the specified release, "
            "ordered by date. Optionally include dates with no data."
        ),
        params=(
            _RELEASE_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _SORT_ORDER_PARAM,
            _INCLUDE_RELEASE_DATES_WITH_NO_DATA_PARAM,
        ),
        examples=(
            "fredq release-dates 53 --limit 5",
            "fredq release-dates 10 --sort-order desc",
        ),
    ),
    CommandSpec(
        name="release-series",
        path="/fred/release/series",
        summary="List series belonging to one FRED release.",
        description=(
            "Return the series records published under the specified release. "
            "Supports tag filtering, attribute filtering, and sorting."
        ),
        params=(
            _RELEASE_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_RELEASE_SERIES),
            _SORT_ORDER_PARAM,
            _FILTER_VARIABLE_SERIES_PARAM,
            _FILTER_VALUE_PARAM,
            _TAG_NAMES_PARAM,
            _EXCLUDE_TAG_NAMES_PARAM,
        ),
        examples=(
            "fredq release-series 53 --limit 5",
            "fredq release-series 175 --tag-names 'usa;annual' --limit 10",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
        mutually_dependent_params=(frozenset({"filter_variable", "filter_value"}),),
        requires_partner=(("exclude_tag_names", "tag_names"),),
    ),
    CommandSpec(
        name="release-sources",
        path="/fred/release/sources",
        summary="List sources for one FRED release.",
        description=(
            "Return the source records that publish or maintain the data for "
            "the specified release. Includes source ID, name, and link."
        ),
        params=(
            _RELEASE_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
        ),
        examples=(
            "fredq release-sources 53",
            "fredq release-sources 10",
        ),
    ),
    CommandSpec(
        name="release-tags",
        path="/fred/release/tags",
        summary="List tags for one FRED release.",
        description=(
            "Return tags associated with the series published under the "
            "specified release. Supports group and text filtering."
        ),
        params=(
            _RELEASE_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _TAG_NAMES_PARAM,
            _TAG_GROUP_ID_PARAM,
            _SEARCH_TEXT_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_TAG_LIKE),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq release-tags 53 --limit 10",
            "fredq release-tags 175 --tag-group-id geo",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
    ),
    CommandSpec(
        name="release-related-tags",
        path="/fred/release/related_tags",
        summary="List tags related to a release and existing tag filter.",
        description=(
            "Return tags related to series in the specified release that are "
            "also tagged with the given tag names. Use to drill down into a "
            "release tag hierarchy."
        ),
        params=(
            _RELEASE_ID_PARAM,
            _TAG_NAMES_REQUIRED_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _TAG_GROUP_ID_PARAM,
            _SEARCH_TEXT_PARAM,
            _EXCLUDE_TAG_NAMES_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_TAG_LIKE),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq release-related-tags 53 --tag-names usa",
            "fredq release-related-tags 175 --tag-names 'usa;annual' --limit 5",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
    ),
    CommandSpec(
        name="release-tables",
        path="/fred/release/tables",
        summary="Fetch the hierarchical data table for one FRED release.",
        description=(
            "Return the release's element tree — the hierarchical table of "
            "categories, series, and observations used in FRED release reports. "
            "The response is a nested structure keyed by element ID."
        ),
        params=(
            _RELEASE_ID_PARAM,
            ParamSpec(
                name="element_id",
                cli_name="element-id",
                kind=ParamKind.INTEGER,
                help=(
                    "Specific element ID within the release table to retrieve. "
                    "Omit to retrieve the full table."
                ),
                metavar="ID",
                min_value=1,
            ),
            ParamSpec(
                name="include_observation_values",
                cli_name="include-observation-values",
                kind=ParamKind.BOOLEAN,
                help=(
                    "Include the latest observation value for each series "
                    "element in the response (true/false)."
                ),
            ),
            ParamSpec(
                name="observation_date",
                cli_name="observation-date",
                kind=ParamKind.DATE,
                help=(
                    "Observation date (YYYY-MM-DD) to use when "
                    "--include-observation-values is set."
                ),
                metavar="DATE",
            ),
        ),
        examples=(
            "fredq release-tables 53",
            "fredq release-tables 53 --include-observation-values",
        ),
        notes=("The response is a hierarchical JSON tree, not a flat array.",),
    ),
    # ------------------------------------------------------------------
    # Group 4 — Tags (3 endpoints)
    # ------------------------------------------------------------------
    CommandSpec(
        name="tags-series",
        path="/fred/tags/series",
        summary="List series matching a set of FRED tags.",
        description=(
            "Return series records that are tagged with all of the specified "
            "tag names. Supports tag exclusion, sorting, and pagination."
        ),
        params=(
            _TAG_NAMES_POSITIONAL_PARAM,
            _EXCLUDE_TAG_NAMES_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_TAGS_SERIES),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq tags-series usa --limit 5",
            "fredq tags-series 'usa;annual' --limit 3",
        ),
        notes=(
            "Tag lists use semicolons as separators (e.g. 'usa;annual').",
            "--exclude-tag-names may optionally accompany the required TAGS argument.",
        ),
    ),
    CommandSpec(
        name="tags",
        path="/fred/tags",
        summary="List all FRED tags.",
        description=(
            "Return the full catalog of FRED tags. Each record includes the "
            "tag name, group ID, notes, creation date, and series count."
        ),
        params=(
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _TAG_NAMES_PARAM,
            _TAG_GROUP_ID_PARAM,
            _SEARCH_TEXT_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_TAG_LIKE),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq tags --limit 10",
            "fredq tags --tag-group-id geo --order-by name --sort-order asc",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
    ),
    CommandSpec(
        name="related-tags",
        path="/fred/related_tags",
        summary="List tags related to an existing tag filter.",
        description=(
            "Return tags that appear alongside the specified tag names across "
            "FRED series. Use to discover related tags when narrowing a series "
            "search."
        ),
        params=(
            _TAG_NAMES_POSITIONAL_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _TAG_GROUP_ID_PARAM,
            _SEARCH_TEXT_PARAM,
            _EXCLUDE_TAG_NAMES_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_TAG_LIKE),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq related-tags usa --limit 10",
            "fredq related-tags 'usa;annual' --limit 5",
        ),
        notes=("Tag lists use semicolons as separators (e.g. 'usa;annual').",),
    ),
    # ------------------------------------------------------------------
    # Group 5 — Sources (3 endpoints)
    # ------------------------------------------------------------------
    CommandSpec(
        name="sources",
        path="/fred/sources",
        summary="List all FRED data sources.",
        description=(
            "Return the full catalog of FRED sources. Each record includes "
            "source ID, name, and link."
        ),
        params=(
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_SOURCES),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq sources --limit 10",
            "fredq sources --order-by name --sort-order asc",
        ),
    ),
    CommandSpec(
        name="source",
        path="/fred/source",
        summary="Show metadata for one FRED source.",
        description=(
            "Return the source record for the given source ID, including name and link."
        ),
        params=(
            _SOURCE_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
        ),
        examples=(
            "fredq source 1",
            "fredq source 18",
        ),
    ),
    CommandSpec(
        name="source-releases",
        path="/fred/source/releases",
        summary="List releases published by one FRED source.",
        description=(
            "Return the release records published or maintained by the specified "
            "source. Includes release ID, name, and press-release flag."
        ),
        params=(
            _SOURCE_ID_PARAM,
            _REALTIME_START_PARAM,
            _REALTIME_END_PARAM,
            _LIMIT_PARAM,
            _OFFSET_PARAM,
            _order_by_param(_ORDER_BY_SOURCE_RELEASES),
            _SORT_ORDER_PARAM,
        ),
        examples=(
            "fredq source-releases 1 --limit 5",
            "fredq source-releases 3 --order-by name",
        ),
    ),
)

# ---------------------------------------------------------------------------
# GeoFRED (Maps) API — shared param constants
# ---------------------------------------------------------------------------

_GEOFRED_REGION_TYPES: Final[tuple[str, ...]] = (
    "bea",
    "msa",
    "frb",
    "necta",
    "state",
    "country",
    "county",
    "censusregion",
    "censusdivision",
)

_REGION_TYPE_PARAM: Final[ParamSpec] = ParamSpec(
    name="region_type",
    cli_name="region-type",
    kind=ParamKind.STRING,
    help=(
        "Region type: bea, msa, frb, necta, state, country, county, "
        "censusregion, censusdivision."
    ),
    required=True,
    allowed_values=_GEOFRED_REGION_TYPES,
    metavar="REGION",
)

_DATE_PARAM: Final[ParamSpec] = ParamSpec(
    name="date",
    cli_name="date",
    kind=ParamKind.DATE,
    help="Date to fetch data for (YYYY-MM-DD).",
    metavar="DATE",
)

_DATE_REQUIRED_PARAM: Final[ParamSpec] = ParamSpec(
    name="date",
    cli_name="date",
    kind=ParamKind.DATE,
    help="Date to fetch data for (YYYY-MM-DD).",
    required=True,
    metavar="DATE",
)

_START_DATE_PARAM: Final[ParamSpec] = ParamSpec(
    name="start_date",
    cli_name="start-date",
    kind=ParamKind.DATE,
    help="Earliest date (YYYY-MM-DD).",
    metavar="DATE",
)

_SEASON_PARAM: Final[ParamSpec] = ParamSpec(
    name="season",
    cli_name="season",
    kind=ParamKind.STRING,
    help="Seasonality code: SA, NSA, SSA, SAAR, NSAAR.",
    required=True,
    allowed_values=("SA", "NSA", "SSA", "SAAR", "NSAAR"),
    metavar="SEASON",
)

_AGGREGATION_METHOD_PARAM: Final[ParamSpec] = ParamSpec(
    name="aggregation_method",
    cli_name="aggregation-method",
    kind=ParamKind.STRING,
    help="Aggregation method: avg, sum, eop.",
    allowed_values=("avg", "sum", "eop"),
    metavar="METHOD",
)

_UNITS_DISPLAY_PARAM: Final[ParamSpec] = ParamSpec(
    name="units",
    cli_name="units",
    kind=ParamKind.STRING,
    help=(
        "Units display name (e.g. 'Dollars', 'Percent', 'Index 2017=100'). "
        "Get from 'fredq geofred series-group <id>'."
    ),
    required=True,
    metavar="UNITS",
)

# GeoFRED regional/data accepts the lowercase single-letter frequency codes
# that match frequency_short from series-group (e.g. "a" for Annual).
# The full set observed in practice mirrors the core FRED base frequencies.
_GEOFRED_FREQUENCY_PARAM: Final[ParamSpec] = ParamSpec(
    name="frequency",
    cli_name="frequency",
    kind=ParamKind.STRING,
    help=(
        "Frequency code matching frequency_short from 'geofred series-group': "
        "d (daily), w (weekly), bw (biweekly), m (monthly), "
        "q (quarterly), sa (semiannual), a (annual)."
    ),
    required=True,
    allowed_values=_FREQUENCY_BASE,
    metavar="FREQ",
)

# ---------------------------------------------------------------------------
# GeoFRED COMMANDS (appended after source-releases)
# ---------------------------------------------------------------------------

_GEOFRED_COMMANDS: Final[tuple[CommandSpec, ...]] = (
    CommandSpec(
        name="series-group",
        path="/geofred/series/group",
        group="geofred",
        summary="Show GeoFRED series group metadata (region, season, frequency, units).",  # noqa: E501
        description=(
            "Return the series_group ID, season, frequency, units (display names), "
            "and observation range needed to call geofred regional-data."
        ),
        params=(_SERIES_ID_PARAM,),
        examples=("fredq geofred series-group WIPCPI",),
    ),
    CommandSpec(
        name="series-data",
        path="/geofred/series/data",
        group="geofred",
        summary="Fetch regional time-series data for one FRED series.",
        description=(
            "Return a time series of regional observation values for the "
            "specified FRED series. Each observation includes the region name, "
            "FIPS code, date, and value."
        ),
        params=(
            _SERIES_ID_PARAM,
            _DATE_PARAM,
            _START_DATE_PARAM,
        ),
        examples=(
            "fredq geofred series-data WIPCPI",
            ("fredq geofred series-data WIPCPI --start-date 2020-01-01"),
        ),
    ),
    CommandSpec(
        name="regional-data",
        path="/geofred/regional/data",
        group="geofred",
        summary="Fetch a regional snapshot — all regions for one date.",
        description=(
            "Return observation values for all regions of the specified series "
            "group on a single date. Each record includes the region name, "
            "FIPS code, and observation value."
        ),
        params=(
            ParamSpec(
                name="series_group",
                cli_name="series-group",
                kind=ParamKind.STRING,
                help=(
                    "GeoFRED series group ID (e.g. 882). "
                    "Discover via 'fredq geofred series-group <id>'."
                ),
                positional=True,
                required=True,
                metavar="ID",
            ),
            _REGION_TYPE_PARAM,
            _DATE_REQUIRED_PARAM,
            _SEASON_PARAM,
            _GEOFRED_FREQUENCY_PARAM,
            _UNITS_DISPLAY_PARAM,
            _START_DATE_PARAM,
            _AGGREGATION_METHOD_PARAM,
        ),
        examples=(
            (
                "fredq geofred regional-data 882 "
                "--region-type state --date 2020-01-01 "
                "--season NSA --frequency a --units Dollars"
            ),
        ),
        notes=(
            (
                "Run 'fredq geofred series-group <id>' first to "
                "discover the correct series-group ID, --season, and --units "
                "values."
            ),
            (
                "--frequency takes the API code, not the display name: "
                "use 'a' for Annual, 'q' for Quarterly, 'm' for Monthly, "
                "'w' for Weekly, 'd' for Daily."
            ),
        ),
    ),
    CommandSpec(
        name="shapes",
        path="/geofred/shapes/file",
        group="geofred",
        output_to_file=True,
        summary="Download a GeoJSON shape file for a GeoFRED region type.",
        description=(
            "Download the polygon boundary file for the specified region type "
            "and write it to --out. The response is GeoJSON."
        ),
        params=(
            ParamSpec(
                name="shape",
                cli_name="shape",
                kind=ParamKind.STRING,
                help=(
                    "Region polygon set: bea, msa, frb, necta, state, country, county, "
                    "censusregion, censusdivision."
                ),
                positional=True,
                required=True,
                allowed_values=_GEOFRED_REGION_TYPES,
                metavar="SHAPE",
            ),
        ),
        examples=("fredq geofred shapes state --out states.geojson",),
        notes=(
            "Output is GeoJSON. The msa shape is ~1.6 MB.",
            (
                "Coordinates are quantized integers, not WGS84. To render on a "
                "map you must apply the transform parameters embedded in the "
                "response to dequantize."
            ),
        ),
    ),
)

COMMANDS: Final[tuple[CommandSpec, ...]] = _CORE_COMMANDS + _GEOFRED_COMMANDS


COMMANDS_BY_NAME: Final[dict[str, CommandSpec]] = {
    command.name: command for command in COMMANDS
}
