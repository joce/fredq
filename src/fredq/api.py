"""Public synchronous fredq API.

Every method/function performs one HTTP call and returns the full parsed
FRED payload as a dict (typed models arrive endpoint-by-endpoint in Part
3), except ``Series.observations`` which returns a typed
:class:`~fredq.frames.Observations` frame. Kwargs mirror FRED wire
parameter names exactly as the CLI's command metadata spells them.

GeoFRED endpoints are deliberately absent (spec Non-goals); ``raw()``
reaches them for anyone who needs them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Final, TypeAlias, cast

from fredq import _core
from fredq._bridge import run
from fredq._core import configure  # re-exported via fredq.__init__
from fredq.commands import COMMANDS_BY_NAME
from fredq.exceptions import FredApiError, FredClientUsageError
from fredq.frames import Observations, build_observations
from fredq.models import (
    CategoriesResult,
    CategoryInfo,
    ReleaseDatesResult,
    ReleaseInfo,
    ReleaseSourcesResult,
    ReleasesResult,
    SeriesInfo,
    SeriesListResult,
    SourceInfo,
    SourcesResult,
    TagsResult,
)

if TYPE_CHECKING:
    from datetime import date

DateLike: TypeAlias = "str | date | datetime"

GEOFRED_EXCLUDED: Final[frozenset[str]] = frozenset(
    {"series-group", "series-data", "regional-data", "shapes"}
)
"""Commands deliberately absent from the library surface (spec Non-goals)."""

__all__ = [
    "GEOFRED_EXCLUDED",
    "Category",
    "DateLike",
    "Release",
    "Series",
    "Source",
    "configure",
    "raw",
    "related_tags",
    "release_calendar",
    "releases",
    "search_series",
    "search_series_related_tags",
    "search_series_tags",
    "series_updates",
    "sources",
    "tag_series",
    "tags",
]


def _values(**kwargs: object) -> dict[str, object]:
    """Drop unset (None) kwargs; keys are wire param names.

    Returns:
        dict[str, object]: The present (non-None) keyword arguments.
    """

    return {key: value for key, value in kwargs.items() if value is not None}


def _call(command_name: str, values: dict[str, object]) -> dict[str, Any]:
    """Run one endpoint call on the bridge.

    Returns:
        dict[str, Any]: The parsed payload.
    """

    return run(_core.call_endpoint(command_name, values=values))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _unwrap_single(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Unwrap FRED's one-element entity list; malformed contract on violation.

    Single-entity endpoints (series show, category show, ...) answer with
    a one-element list under their plural key. Corpus evidence: always
    exactly one element on success (bad ids fail earlier as FRED 400s).

    Returns:
        dict[str, Any]: The single entity record.

    Raises:
        FredApiError: If ``key`` is missing or has != 1 element
            (``error_code=None`` marks the malformed-response contract).
    """

    raw_records = payload.get(key)
    if not isinstance(raw_records, list):
        message = f"expected exactly one {key!r} record, got no list"
        raise FredApiError(error_message=message)
    records = cast("list[object]", raw_records)
    if len(records) != 1:
        message = f"expected exactly one {key!r} record, got {len(records)}"
        raise FredApiError(error_message=message)
    record = records[0]
    if not isinstance(record, dict):
        message = f"{key!r} record is not an object"
        raise FredApiError(error_message=message)
    return cast("dict[str, Any]", record)


class Series:
    """A FRED series, addressed by its series-ID string (e.g. "DGS10")."""

    def __init__(self, series_id: str) -> None:
        """Bind a series ID for subsequent calls."""

        self.series_id = series_id.strip()

    def __repr__(self) -> str:
        """Return an eval-able repr naming the class and id.

        Returns:
            str: The repr string.
        """

        return f"Series({self.series_id!r})"

    def info(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> SeriesInfo:
        """Fetch the series record (title, units, frequency, ...).

        Returns:
            SeriesInfo: The corpus-gated series record.
        """

        payload = _call(
            "series",
            _values(
                series_id=self.series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )
        return SeriesInfo.model_validate(_unwrap_single(payload, "seriess"))

    def observations(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        *,
        observation_start: DateLike | None = None,
        observation_end: DateLike | None = None,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        units: str | None = None,
        frequency: str | None = None,
    ) -> Observations:
        """Fetch observations (values) for this series.

        Returns:
            Observations: Rows as polars columns, envelope as ``meta``.
        """

        payload = _call(
            "series-observations",
            _values(
                series_id=self.series_id,
                observation_start=observation_start,
                observation_end=observation_end,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                units=units,
                frequency=frequency,
            ),
        )
        return build_observations(payload, fetched_at=_now_utc())

    def vintage_dates(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """List vintage dates (revision dates) for this series.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "series-vintagedates",
            _values(
                series_id=self.series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                limit=limit,
                offset=offset,
                sort_order=sort_order,
            ),
        )

    def categories(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> CategoriesResult:
        """List categories that contain this series.

        Returns:
            CategoriesResult: The category list.
        """

        payload = _call(
            "series-categories",
            _values(
                series_id=self.series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )
        return CategoriesResult.model_validate(payload)

    def tags(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
    ) -> TagsResult:
        """List tags assigned to this series.

        Returns:
            TagsResult: The paginated tag list.
        """

        payload = _call(
            "series-tags",
            _values(
                series_id=self.series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order,
            ),
        )
        return TagsResult.model_validate(payload)

    def release(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> ReleaseInfo:
        """Show the release that this series belongs to.

        Returns:
            ReleaseInfo: The corpus-gated release record.
        """

        payload = _call(
            "series-release",
            _values(
                series_id=self.series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )
        return ReleaseInfo.model_validate(_unwrap_single(payload, "releases"))


class Category:
    """A FRED category, addressed by its integer ID (the tree root is 0)."""

    def __init__(self, category_id: int) -> None:
        """Bind a category ID for subsequent calls."""

        self.category_id = category_id

    def __repr__(self) -> str:
        """Return an eval-able repr naming the class and id.

        Returns:
            str: The repr string.
        """

        return f"Category({self.category_id!r})"

    def info(self) -> CategoryInfo:
        """Fetch the category record (name, parent ID).

        FRED's category endpoint takes no realtime parameters, unlike the
        other entity ``info()`` methods — the zero-argument signature is
        deliberate, not an omission.

        Returns:
            CategoryInfo: The corpus-gated category record.
        """

        payload = _call("category", _values(category_id=self.category_id))
        return CategoryInfo.model_validate(_unwrap_single(payload, "categories"))

    def children(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> CategoriesResult:
        """List direct child categories of this category.

        Returns:
            CategoriesResult: The category list.
        """

        payload = _call(
            "category-children",
            _values(
                category_id=self.category_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )
        return CategoriesResult.model_validate(payload)

    def related(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> CategoriesResult:
        """List categories related to this category.

        Returns:
            CategoriesResult: The category list.
        """

        payload = _call(
            "category-related",
            _values(
                category_id=self.category_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )
        return CategoriesResult.model_validate(payload)

    def series(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
        filter_variable: str | None = None,
        filter_value: str | None = None,
        tag_names: list[str] | str | None = None,
        exclude_tag_names: list[str] | str | None = None,
    ) -> SeriesListResult:
        """List series belonging to this category.

        Returns:
            SeriesListResult: The paginated series list.
        """

        payload = _call(
            "category-series",
            _values(
                category_id=self.category_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                limit=limit,
                offset=offset,
                order_by=order_by,
                sort_order=sort_order,
                filter_variable=filter_variable,
                filter_value=filter_value,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names,
            ),
        )
        return SeriesListResult.model_validate(payload)

    def tags(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        tag_names: list[str] | str | None = None,
        tag_group_id: str | None = None,
        search_text: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
    ) -> TagsResult:
        """List tags for series in this category.

        Returns:
            TagsResult: The paginated tag list.
        """

        payload = _call(
            "category-tags",
            _values(
                category_id=self.category_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                tag_group_id=tag_group_id,
                search_text=search_text,
                limit=limit,
                offset=offset,
                order_by=order_by,
                sort_order=sort_order,
            ),
        )
        return TagsResult.model_validate(payload)

    def related_tags(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        tag_names: list[str] | str,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        tag_group_id: str | None = None,
        search_text: str | None = None,
        exclude_tag_names: list[str] | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
    ) -> TagsResult:
        """List tags related to this category and an existing tag filter.

        Returns:
            TagsResult: The paginated tag list.
        """

        payload = _call(
            "category-related-tags",
            _values(
                category_id=self.category_id,
                tag_names=tag_names,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_group_id=tag_group_id,
                search_text=search_text,
                exclude_tag_names=exclude_tag_names,
                limit=limit,
                offset=offset,
                order_by=order_by,
                sort_order=sort_order,
            ),
        )
        return TagsResult.model_validate(payload)


class Release:
    """A FRED release, addressed by its integer ID (e.g. 53 = GDP)."""

    def __init__(self, release_id: int) -> None:
        """Bind a release ID for subsequent calls."""

        self.release_id = release_id

    def __repr__(self) -> str:
        """Return an eval-able repr naming the class and id.

        Returns:
            str: The repr string.
        """

        return f"Release({self.release_id!r})"

    def info(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> ReleaseInfo:
        """Fetch the release record (name, press-release flag, links).

        Returns:
            ReleaseInfo: The corpus-gated release record.
        """

        payload = _call(
            "release",
            _values(
                release_id=self.release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )
        return ReleaseInfo.model_validate(_unwrap_single(payload, "releases"))

    def dates(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_order: str | None = None,
        include_release_dates_with_no_data: bool | None = None,
    ) -> ReleaseDatesResult:
        """List publication dates for this release.

        Returns:
            ReleaseDatesResult: The paginated release dates.
        """

        payload = _call(
            "release-dates",
            _values(
                release_id=self.release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                limit=limit,
                offset=offset,
                sort_order=sort_order,
                include_release_dates_with_no_data=include_release_dates_with_no_data,
            ),
        )
        return ReleaseDatesResult.model_validate(payload)

    def series(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
        filter_variable: str | None = None,
        filter_value: str | None = None,
        tag_names: list[str] | str | None = None,
        exclude_tag_names: list[str] | str | None = None,
    ) -> SeriesListResult:
        """List series belonging to this release.

        Returns:
            SeriesListResult: The paginated series list.
        """

        payload = _call(
            "release-series",
            _values(
                release_id=self.release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                limit=limit,
                offset=offset,
                order_by=order_by,
                sort_order=sort_order,
                filter_variable=filter_variable,
                filter_value=filter_value,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names,
            ),
        )
        return SeriesListResult.model_validate(payload)

    def sources(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> ReleaseSourcesResult:
        """List sources for this release.

        Returns:
            ReleaseSourcesResult: The sources for this release.
        """

        payload = _call(
            "release-sources",
            _values(
                release_id=self.release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )
        return ReleaseSourcesResult.model_validate(payload)

    def tags(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        tag_names: list[str] | str | None = None,
        tag_group_id: str | None = None,
        search_text: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
    ) -> TagsResult:
        """List tags for this release.

        Returns:
            TagsResult: The paginated tag list.
        """

        payload = _call(
            "release-tags",
            _values(
                release_id=self.release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                tag_group_id=tag_group_id,
                search_text=search_text,
                limit=limit,
                offset=offset,
                order_by=order_by,
                sort_order=sort_order,
            ),
        )
        return TagsResult.model_validate(payload)

    def related_tags(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        tag_names: list[str] | str,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        tag_group_id: str | None = None,
        search_text: str | None = None,
        exclude_tag_names: list[str] | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
    ) -> TagsResult:
        """List tags related to this release and an existing tag filter.

        Returns:
            TagsResult: The paginated tag list.
        """

        payload = _call(
            "release-related-tags",
            _values(
                release_id=self.release_id,
                tag_names=tag_names,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_group_id=tag_group_id,
                search_text=search_text,
                exclude_tag_names=exclude_tag_names,
                limit=limit,
                offset=offset,
                order_by=order_by,
                sort_order=sort_order,
            ),
        )
        return TagsResult.model_validate(payload)

    def tables(
        self,
        *,
        element_id: int | None = None,
        include_observation_values: bool | None = None,
        observation_date: DateLike | None = None,
    ) -> dict[str, Any]:
        """Fetch the hierarchical data table for this release.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "release-tables",
            _values(
                release_id=self.release_id,
                element_id=element_id,
                include_observation_values=include_observation_values,
                observation_date=observation_date,
            ),
        )


class Source:
    """A FRED source, addressed by its integer ID (e.g. 1 = Board of Governors)."""

    def __init__(self, source_id: int) -> None:
        """Bind a source ID for subsequent calls."""

        self.source_id = source_id

    def __repr__(self) -> str:
        """Return an eval-able repr naming the class and id.

        Returns:
            str: The repr string.
        """

        return f"Source({self.source_id!r})"

    def info(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> SourceInfo:
        """Fetch the source record (name, link).

        Returns:
            SourceInfo: The corpus-gated source record.
        """

        payload = _call(
            "source",
            _values(
                source_id=self.source_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )
        return SourceInfo.model_validate(_unwrap_single(payload, "sources"))

    def releases(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
    ) -> ReleasesResult:
        """List releases published by this source.

        Returns:
            ReleasesResult: The paginated release list.
        """

        payload = _call(
            "source-releases",
            _values(
                source_id=self.source_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                limit=limit,
                offset=offset,
                order_by=order_by,
                sort_order=sort_order,
            ),
        )
        return ReleasesResult.model_validate(payload)


def search_series(  # noqa: PLR0913 - one keyword-only arg per wire param.
    search_text: str,
    *,
    search_type: str | None = None,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
    filter_variable: str | None = None,
    filter_value: str | None = None,
    tag_names: list[str] | str | None = None,
    exclude_tag_names: list[str] | str | None = None,
) -> SeriesListResult:
    """Search FRED series by keyword.

    Returns:
        SeriesListResult: The paginated series list.
    """

    payload = _call(
        "series-search",
        _values(
            search_text=search_text,
            search_type=search_type,
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            limit=limit,
            offset=offset,
            order_by=order_by,
            sort_order=sort_order,
            filter_variable=filter_variable,
            filter_value=filter_value,
            tag_names=tag_names,
            exclude_tag_names=exclude_tag_names,
        ),
    )
    return SeriesListResult.model_validate(payload)


def search_series_tags(  # noqa: PLR0913 - one keyword-only arg per wire param.
    series_search_text: str,
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    tag_names: list[str] | str | None = None,
    tag_group_id: str | None = None,
    tag_search_text: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
) -> dict[str, Any]:
    """List tags for a series full-text search.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
        "series-search-tags",
        _values(
            series_search_text=series_search_text,
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            tag_names=tag_names,
            tag_group_id=tag_group_id,
            tag_search_text=tag_search_text,
            limit=limit,
            offset=offset,
            order_by=order_by,
            sort_order=sort_order,
        ),
    )


def search_series_related_tags(  # noqa: PLR0913 - one keyword-only arg per wire param.
    series_search_text: str,
    tag_names: list[str] | str,
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    tag_group_id: str | None = None,
    tag_search_text: str | None = None,
    exclude_tag_names: list[str] | str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
) -> dict[str, Any]:
    """List tags related to a search and existing tag filter.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
        "series-search-related-tags",
        _values(
            series_search_text=series_search_text,
            tag_names=tag_names,
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            tag_group_id=tag_group_id,
            tag_search_text=tag_search_text,
            exclude_tag_names=exclude_tag_names,
            limit=limit,
            offset=offset,
            order_by=order_by,
            sort_order=sort_order,
        ),
    )


def series_updates(  # noqa: PLR0913 - one keyword-only arg per wire param.
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    limit: int | None = None,
    offset: int | None = None,
    filter_value: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """List recently updated FRED series.

    ``start_time``/``end_time`` use FRED's compact ``YYYYMMDDHhmm`` format
    (e.g. ``"202401011200"``), not ISO dates.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
        "series-updates",
        _values(
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            limit=limit,
            offset=offset,
            filter_value=filter_value,
            start_time=start_time,
            end_time=end_time,
        ),
    )


def releases(  # noqa: PLR0913 - one keyword-only arg per wire param.
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
) -> ReleasesResult:
    """List all FRED economic data releases.

    Returns:
        ReleasesResult: The paginated release list.
    """

    payload = _call(
        "releases",
        _values(
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            limit=limit,
            offset=offset,
            order_by=order_by,
            sort_order=sort_order,
        ),
    )
    return ReleasesResult.model_validate(payload)


def release_calendar(  # noqa: PLR0913 - one keyword-only arg per wire param.
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
    include_release_dates_with_no_data: bool | None = None,
) -> ReleaseDatesResult:
    """List release dates across all FRED releases.

    Returns:
        ReleaseDatesResult: The paginated release dates.
    """

    payload = _call(
        "releases-dates",
        _values(
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            limit=limit,
            offset=offset,
            order_by=order_by,
            sort_order=sort_order,
            include_release_dates_with_no_data=include_release_dates_with_no_data,
        ),
    )
    return ReleaseDatesResult.model_validate(payload)


def sources(  # noqa: PLR0913 - one keyword-only arg per wire param.
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
) -> SourcesResult:
    """List all FRED data sources.

    Returns:
        SourcesResult: The paginated source list.
    """

    payload = _call(
        "sources",
        _values(
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            limit=limit,
            offset=offset,
            order_by=order_by,
            sort_order=sort_order,
        ),
    )
    return SourcesResult.model_validate(payload)


def tags(  # noqa: PLR0913 - one keyword-only arg per wire param.
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    tag_names: list[str] | str | None = None,
    tag_group_id: str | None = None,
    search_text: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
) -> TagsResult:
    """List all FRED tags.

    Returns:
        TagsResult: The paginated tag list.
    """

    payload = _call(
        "tags",
        _values(
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            tag_names=tag_names,
            tag_group_id=tag_group_id,
            search_text=search_text,
            limit=limit,
            offset=offset,
            order_by=order_by,
            sort_order=sort_order,
        ),
    )
    return TagsResult.model_validate(payload)


def tag_series(  # noqa: PLR0913 - one keyword-only arg per wire param.
    tag_names: list[str] | str,
    *,
    exclude_tag_names: list[str] | str | None = None,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
) -> SeriesListResult:
    """List series matching a set of FRED tags.

    Returns:
        SeriesListResult: The paginated series list.
    """

    payload = _call(
        "tags-series",
        _values(
            tag_names=tag_names,
            exclude_tag_names=exclude_tag_names,
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            limit=limit,
            offset=offset,
            order_by=order_by,
            sort_order=sort_order,
        ),
    )
    return SeriesListResult.model_validate(payload)


def related_tags(  # noqa: PLR0913 - one keyword-only arg per wire param.
    tag_names: list[str] | str,
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    tag_group_id: str | None = None,
    search_text: str | None = None,
    exclude_tag_names: list[str] | str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
) -> TagsResult:
    """List tags related to an existing tag filter.

    Returns:
        TagsResult: The paginated tag list.
    """

    payload = _call(
        "related-tags",
        _values(
            tag_names=tag_names,
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            tag_group_id=tag_group_id,
            search_text=search_text,
            exclude_tag_names=exclude_tag_names,
            limit=limit,
            offset=offset,
            order_by=order_by,
            sort_order=sort_order,
        ),
    )
    return TagsResult.model_validate(payload)


def raw(command: str, **params: object) -> dict[str, Any]:
    """Call any fredq command by name; return the parsed payload.

    The escape hatch: reaches every command the CLI knows, including the
    geofred family that has no first-class library surface. Parameters
    are validated exactly like every other library call.

    Returns:
        dict[str, Any]: The full parsed payload.

    Raises:
        FredClientUsageError: If ``command`` is not a known command name.
    """

    if command not in COMMANDS_BY_NAME:
        message = f"unknown command: {command!r}"
        raise FredClientUsageError(message)
    return _call(command, dict(params))
