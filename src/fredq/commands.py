"""FRED command metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from fredq.client import FRED_BASE_URL
from fredq.params import ParamKind, ParamSpec

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

    @property
    def fred_url(self) -> str:
        """Return the full FRED URL for this endpoint."""

        return f"{FRED_BASE_URL}{self.path}"


_SERIES_ID_PARAM: Final[ParamSpec] = ParamSpec(
    name="series_id",
    cli_name="series-id",
    kind=ParamKind.STRING,
    help="FRED series identifier (e.g. GNPCA, DGS10, CPIAUCSL).",
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


# v1 starts with two endpoints to prove the pattern; remaining ~29 added
# incrementally. See AGENTS.md "Architecture" + docs/v2-geofred.md.
COMMANDS: Final[tuple[CommandSpec, ...]] = (
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
            "fredq series --series-id GNPCA",
            "fredq series --series-id DGS10 --realtime-start 2024-01-01",
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
            "fredq series-observations --series-id GNPCA",
            (
                "fredq series-observations --series-id CPIAUCSL "
                "--units pch --frequency m"
            ),
        ),
        notes=(
            (
                "Returns the full FRED envelope including count/offset/limit; "
                "the observations array lives under the 'observations' key."
            ),
        ),
    ),
)


COMMANDS_BY_NAME: Final[dict[str, CommandSpec]] = {
    command.name: command for command in COMMANDS
}
