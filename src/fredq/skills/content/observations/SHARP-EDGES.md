# Sharp edges: observations

## FRED's missing-value sentinel is the string `"."`, never `NaN`

**Severity:** medium

FRED encodes a missing observation as the literal string `"."` on the
wire, for a market closure, a bank holiday, or a not-yet-published point
inside an otherwise-populated window.

Wrong way: testing for a missing value with `value != value` (the classic
NaN check) or assuming every row parses to a Python `float`.

Right way: `Observations`' `value` column is `float | None` — fredq
parses `"."` to `None` at build time (`fredq.frames.build_observations`).
Test with `is None`, and remember polars will show it as a `null` cell,
not `NaN`, in `.to_polars()`.

Evidence: 2026-07-05, corpus-confirmed
(`series-observations/DEXCAUS_holidays`: 2023-12-25, Christmas, is a `"."`
row between two priced days).

## Future observation windows return 200 + empty, not an error

**Severity:** low

Asking for a window that has not happened yet is not a client mistake as
far as FRED is concerned.

Wrong way: wrapping an `observations()` call for a not-yet-elapsed date
range in a `try`/`except FredApiError`, expecting FRED to reject it.

Right way: check `obs.meta.count` (or `obs.to_polars().height`) — `0` is
a valid, successful answer when the requested window is entirely in the
future; nothing raised, nothing to catch.

Evidence: 2026-07-05, corpus-confirmed
(`series-observations/DGS10_future-window`, a 2030 window: HTTP 200,
`"observations": []`).
