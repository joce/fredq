# fredq — Positional Primary Arguments (CLI grammar)

Date: 2026-05-31
Status: Approved (design)

## Problem

Every fredq command takes its primary identifier as a named flag
(`--series-id`, `--category-id`, `--release-id`, `--source-id`, `--search-text`,
`--tag-names`). For the common case this is verbose and unidiomatic:

```
fredq series-observations --series-id DGS10
```

A positional primary arg is shorter and matches common CLI conventions
(git/docker put the primary target positionally):

```
fredq series-observations DGS10
```

fredq is pre-1.0 with a single user; breaking the existing flag grammar is
acceptable. No backward-compatibility aliases are required.

## Decision

1. **Each command's single primary required argument becomes a positional.**
   Every other parameter stays a flag.
2. **The old flag for that primary arg is removed** (positional is the only way).
3. Applies to all primary-arg kinds: IDs, search text, and tag lists.
4. Commands with no required argument are unchanged.

## Per-command map

### Positional = ID (metavar `ID`)

`series`, `series-observations`, `series-vintagedates`, `series-categories`,
`series-tags`, `series-release`, `category`, `category-children`,
`category-related`, `category-series`, `category-tags`, `release`,
`release-dates`, `release-series`, `release-sources`, `release-tags`,
`release-tables`, `source`, `source-releases`, `geofred series-group`,
`geofred series-data`

```
fredq series GNPCA
fredq release-series 10
fredq geofred series-data WIPCPI --start-date 2022-01-01
```

### Positional = search text (metavar `TEXT`)

`series-search` (`search-text`), `series-search-tags` (`series-search-text`),
`series-search-related-tags` (`series-search-text`)

```
fredq series-search "10-year treasury"
```

### Positional = tag list (metavar `TAGS`)

`tags-series` (`tag-names`), `related-tags` (`tag-names`)

```
fredq tags-series "usa;monthly"
```

### Positional + a still-required flag

The primary entity is positional; the secondary required arg stays a flag.

```
fredq category-related-tags 32991 --tag-names usa
fredq release-related-tags 10 --tag-names usa
fredq series-search-related-tags "inflation" --tag-names usa
fredq geofred regional-data 882 --region-type state --date 2023-01-01 \
  --season NSA --frequency a --units Dollars
fredq geofred shapes state --out states.geojson
```

- `geofred regional-data`: positional is `series-group` (metavar `ID`); the other
  required args (`region-type`, `date`, `season`, `frequency`, `units`) stay flags.
- `geofred shapes`: positional is `shape` (metavar `SHAPE`); `--out` stays a
  required flag.

### No positional (unchanged)

`releases`, `releases-dates`, `tags`, `sources`, `series-updates`

## Implementation

### `params.py`
- Add `positional: bool = False` to `ParamSpec`.
- The argument's internal `name` (e.g. `series_id`) is unchanged, so the existing
  coercion (`_collect_params`) and cross-parameter validation continue to read by
  name with no changes.

### `cli.py`
- In the per-command argument registration, branch on `spec.positional`:
  - Positional: register with the bare `name` as the argparse positional dest and
    `metavar=spec.metavar`; no leading `--`, no `required=` kwarg.
  - Flag: unchanged.
- Each command has at most one positional, so ordering is trivial; register the
  positional ahead of the optionals.

### `commands.py`
- Mark the shared ID constants (`_SERIES_ID_PARAM`, `_CATEGORY_ID_PARAM`,
  `_RELEASE_ID_PARAM`, `_SOURCE_ID_PARAM`) `positional=True` — they are always the
  primary arg wherever used.
- Mark the search-text params and the geofred `series-group` / `shape` params
  positional.
- `tag-names` splits into two variants:
  - **positional** for `tags-series` and `related-tags` (primary arg),
  - **required flag** for `category-related-tags`, `release-related-tags`,
    `series-search-related-tags` (secondary arg).
- Rewrite every `CommandSpec.examples` entry to the positional form.

## Testing

- Update existing parse/dispatch tests that pass `--series-id` etc. to positional.
- Add cases:
  - positional supplied → parsed into the correct dest,
  - missing positional → argparse usage error, exit code `2`,
  - positional + secondary required flag (e.g. `category-related-tags`),
  - geofred positional commands (`regional-data`, `shapes`).
- Run `pytest -k help` before/after; keep the help suite green.

## Docs

- README: rewrite "Discovering IDs", "Quick Start", and command examples to the
  positional form.
- Root `--help` epilog (`cli.py`): update the discovery examples.
- AGENTS.md: document the positional-primary-arg convention in the help-text rules.

## Out of scope

- Noun-group subcommands (`fredq series observations …`) — evaluated and deferred;
  taxonomy of the plural/list commands does not nest cleanly enough to justify.
- Backward-compatibility aliases for the removed flags.

## Versioning

Breaking CLI grammar change → next release is a minor bump (`0.2.0`) per the
pre-1.0 convention. Released via the normal tag-driven flow.
