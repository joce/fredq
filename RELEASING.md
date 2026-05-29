# Releasing fredq

fredq publishes to [PyPI](https://pypi.org/project/fredq/) from GitHub Actions
(`.github/workflows/publish.yml`) using **Trusted Publishing** (OIDC) — no API
tokens. The workflow runs when a **GitHub Release is published**; a bare
`git push` of a tag does *not* trigger it.

> Trusted publisher and the `pypi` environment (with required-reviewer approval)
> are already configured. No per-release infrastructure setup is needed.

## Cutting a release

Version is single-sourced from `src/fredq/__init__.py` (`__version__`); hatchling
reads it at build time. There is no version field in `pyproject.toml`.

1. Bump `__version__` in `src/fredq/__init__.py` (SemVer).
2. Move the `## [Unreleased]` notes in `CHANGELOG.md` under a new `## [X.Y.Z]`
   heading and update the compare links at the bottom.
3. Commit and push to `main`. Wait for CI to go green.
4. Create the release (this creates the tag *and* triggers publishing):

   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-file path/to/notes.md
   ```

   Write real notes (overview + highlights), not a one-liner.
5. The `publish` job pauses on the `pypi` environment. **Approve the deployment**:
   the run page shows *"Review pending deployments"* → tick `pypi` → *Approve and
   deploy*. After approval it uploads to PyPI.
6. Verify: <https://pypi.org/project/fredq/> shows the new version.

## Verify locally before releasing

```bash
uv build
uvx twine check dist/*
```

The built filenames must carry the version you set in `__init__.py`
(`fredq-X.Y.Z.tar.gz`, `fredq-X.Y.Z-py3-none-any.whl`).
