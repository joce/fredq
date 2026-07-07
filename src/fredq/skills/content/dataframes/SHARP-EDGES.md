# Sharp edges: dataframes

## Inner joins silently drop revised-in rows

**Severity:** medium

`Observations.to_polars()` gives you a plain polars `DataFrame`, so
nothing stops an `how="inner"` join between two vintages of the same
series — but polars' `inner` semantics apply exactly, with no revision
awareness.

Wrong way: joining an older-vintage `Observations` frame to a
newer-vintage one on `date` with `how="inner"` to compare them. Any
`date` that only exists in the newer vintage — a point FRED added or
revised into existence since the older fetch — has no matching row in the
older frame, so `inner` drops it from the result without a warning.

Right way: use `how="full"` (or `"left"` anchored on whichever frame is
more current) and check for post-join nulls to see exactly what changed
between vintages, the same join shape shown in
[README.md](README.md#joining-series-of-different-frequencies).

Evidence: 2026-07-07, live-measured — polars join semantics confirmed
against real revision data
(`series-observations/UNRATE_vintage-2001`, which itself carries two
distinct realtime spans for the same observation date).
