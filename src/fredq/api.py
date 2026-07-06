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
from typing import TYPE_CHECKING, Any, Final, TypeAlias

from fredq import _core
from fredq._bridge import run
from fredq._core import configure  # re-exported via fredq.__init__
from fredq.commands import COMMANDS_BY_NAME
from fredq.exceptions import FredClientUsageError
from fredq.frames import Observations, build_observations

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
    ) -> dict[str, Any]:
        """Fetch the series record (title, units, frequency, ...).

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "series",
            _values(
                series_id=self.series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )

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
    ) -> dict[str, Any]:
        """List categories that contain this series.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "series-categories",
            _values(
                series_id=self.series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )

    def tags(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """List tags assigned to this series.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "series-tags",
            _values(
                series_id=self.series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order,
            ),
        )

    def release(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> dict[str, Any]:
        """Show the release that this series belongs to.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "series-release",
            _values(
                series_id=self.series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )


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

    def info(self) -> dict[str, Any]:
        """Fetch the category record (name, parent ID).

        FRED's category endpoint takes no realtime parameters, unlike the
        other entity ``info()`` methods — the zero-argument signature is
        deliberate, not an omission.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call("category", _values(category_id=self.category_id))

    def children(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> dict[str, Any]:
        """List direct child categories of this category.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "category-children",
            _values(
                category_id=self.category_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )

    def related(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> dict[str, Any]:
        """List categories related to this category.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "category-related",
            _values(
                category_id=self.category_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )

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
    ) -> dict[str, Any]:
        """List series belonging to this category.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
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
    ) -> dict[str, Any]:
        """List tags for series in this category.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
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
    ) -> dict[str, Any]:
        """List tags related to this category and an existing tag filter.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
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
    ) -> dict[str, Any]:
        """Fetch the release record (name, press-release flag, links).

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "release",
            _values(
                release_id=self.release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )

    def dates(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_order: str | None = None,
        include_release_dates_with_no_data: bool | None = None,
    ) -> dict[str, Any]:
        """List publication dates for this release.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
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
    ) -> dict[str, Any]:
        """List series belonging to this release.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
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

    def sources(
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
    ) -> dict[str, Any]:
        """List sources for this release.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "release-sources",
            _values(
                release_id=self.release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )

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
    ) -> dict[str, Any]:
        """List tags for this release.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
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
    ) -> dict[str, Any]:
        """List tags related to this release and an existing tag filter.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
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
    ) -> dict[str, Any]:
        """Fetch the source record (name, link).

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
            "source",
            _values(
                source_id=self.source_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            ),
        )

    def releases(  # noqa: PLR0913 - one keyword-only arg per wire param.
        self,
        *,
        realtime_start: DateLike | None = None,
        realtime_end: DateLike | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """List releases published by this source.

        Returns:
            dict[str, Any]: The full parsed payload.
        """

        return _call(
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
) -> dict[str, Any]:
    """Search FRED series by keyword.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
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
) -> dict[str, Any]:
    """List all FRED economic data releases.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
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


def release_calendar(  # noqa: PLR0913 - one keyword-only arg per wire param.
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
    include_release_dates_with_no_data: bool | None = None,
) -> dict[str, Any]:
    """List release dates across all FRED releases.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
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


def sources(  # noqa: PLR0913 - one keyword-only arg per wire param.
    *,
    realtime_start: DateLike | None = None,
    realtime_end: DateLike | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: str | None = None,
) -> dict[str, Any]:
    """List all FRED data sources.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
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
) -> dict[str, Any]:
    """List all FRED tags.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
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
) -> dict[str, Any]:
    """List series matching a set of FRED tags.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
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
) -> dict[str, Any]:
    """List tags related to an existing tag filter.

    Returns:
        dict[str, Any]: The full parsed payload.
    """

    return _call(
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
