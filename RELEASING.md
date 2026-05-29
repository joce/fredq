# Releasing fredq

fredq publishes to [PyPI](https://pypi.org/project/fredq/) from GitHub Actions
(`.github/workflows/publish.yml`) using **Trusted Publishing** (OIDC) — no API
tokens. The workflow runs when a **GitHub Release is published**; a bare
`git push` of a tag does *not* trigger it.

> Trusted publisher and the `pypi` environment (with required-reviewer approval)
> are already configured. No per-release infrastructure setup is needed.

## Cutting a release

The version is derived from the git tag by `hatch-vcs` — there is **no manual
version bump**. `src/fredq/__init__.py` reads it from a generated `_version.py`
at build time. Tagging `vX.Y.Z` makes the build `X.Y.Z`; commits after a tag get
a `X.Y.(Z+1).devN` version automatically.

1. Move the `## [Unreleased]` notes in `CHANGELOG.md` under a new `## [X.Y.Z]`
   heading and update the compare links at the bottom. Commit and push to `main`.
   Wait for CI to go green.
2. Create the release — this creates the `vX.Y.Z` tag *and* triggers publishing:

   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-file path/to/notes.md
   ```

   Write real notes (overview + highlights), not a one-liner.
3. The `publish` job pauses on the `pypi` environment. **Approve the deployment**:
   the run page shows *"Review pending deployments"* → tick `pypi` → *Approve and
   deploy*. After approval it uploads to PyPI.
4. Verify: <https://pypi.org/project/fredq/> shows the new version.

## Verify locally before releasing

```bash
uv build
uvx twine check dist/*
```

The built filenames carry the version `hatch-vcs` derived from git
(`fredq-X.Y.Z...`). A clean checkout *at* the tag yields exactly `X.Y.Z`; a dirty
tree or post-tag commit yields a `.devN`/`+g<sha>` suffix.
