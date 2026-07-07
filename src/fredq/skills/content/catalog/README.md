# Catalog

Finding a series, releases, sources, and tags — everything upstream of
pulling actual data. Every ID-taking call elsewhere in this skill
(`Series(series_id)`, `Category(category_id)`, `Release(release_id)`,
`Source(source_id)`) expects an ID discovered here first.

## Searching for a series

```python
hits = fredq.search_series("monetary")
series_id = hits.seriess[0].id
info = fredq.Series(series_id).info()
```

`search_series()` returns a `SeriesListResult`: `.seriess` is the ranked
hit list (each a full `SeriesInfo`), `.count` is FRED's total match count
(often far larger than `.seriess` — page with `limit`/`offset`). Chain the
`id` of whichever hit you want into `Series(...)` for the rest of this
skill's calls.

CLI equivalent:

```bash
fredq series search "monetary" --limit 10
```

## Walking the category tree

Category ID `0` is FRED's tree root — walk down from there, or jump
straight to a known category ID:

```python
top_level = fredq.Category(0).children()
```

`children()`/`related()` both return a `CategoriesResult` (`.categories`,
a plain list — FRED's category endpoints carry no pagination envelope).
`Category(0).children()` lists FRED's top-level subject areas (Money,
Banking, & Finance; Prices; National Accounts; ...).

CLI equivalent:

```bash
fredq category children 0
```

## Releases and their sources

```python
release = fredq.Release(53).info()
sources = fredq.Release(53).sources()
```

`Release.info()` returns a `ReleaseInfo` (name, `press_release` flag,
publisher link); `Release.sources()` returns a `ReleaseSourcesResult`
listing the agencies that publish it (53 = GDP, published by the Bureau
of Economic Analysis).

CLI equivalent:

```bash
fredq release show 53
fredq release sources 53
```

## Tags

```python
matches = fredq.tag_series(["usa", "quarterly"])
```

`tag_series()` returns a `SeriesListResult`; a list of tag names is
ANDed together, not ORed — this call finds series carrying **both** the
`usa` and `quarterly` tags, not either.

CLI equivalent (semicolon-joined, matching FRED's wire format):

```bash
fredq tag series "usa;quarterly" --limit 10
```

## Parameters

Full parameter lists, defaults, and examples live in `--help`, not here:

```bash
fredq series search --help
fredq category children --help
fredq release show --help
fredq tag series --help
```

See [SHARP-EDGES.md](SHARP-EDGES.md) for proven pitfalls in this domain.
