# Releasing fredq

fredq publishes to [PyPI](https://pypi.org/project/fredq/) from GitHub Actions
(`.github/workflows/publish.yml`) using **Trusted Publishing** (OIDC) — no API
tokens. **Pushing a `vX.Y.Z` tag starts the whole release**; the only manual
step is approving the PyPI deployment.

> Trusted publisher and the `pypi` environment (with required-reviewer approval)
> are already configured. No per-release infrastructure setup is needed.

## Cutting a release

The version is derived from the git tag by `hatch-vcs` — there is **no manual
version bump**. `src/fredq/__init__.py` reads it from a generated `_version.py`
at build time. Tagging `vX.Y.Z` makes the build `X.Y.Z`; commits after a tag get
a `X.Y.(Z+1).devN` version automatically.

1. Move the `## [Unreleased]` notes in `CHANGELOG.md` under a new `## [X.Y.Z]`
   heading and update the compare links at the bottom. Draft the release notes
   (overview + highlights, not a one-liner) in `docs/release_next.md` and move
   them to `docs/release_vX.Y.Z.md`. Commit and push to `main`; wait for CI to
   go green.
2. Tag the commit on `main` and push the tag:

   ```bash
   git tag vX.Y.Z
   ```

   ```bash
   git push origin vX.Y.Z
   ```

3. The tag push runs `publish.yml`:
   - **validate** — the tag must be exactly `vX.Y.Z` (no prefixes, suffixes or
     leading zeros) and point at a commit on `main`;
   - **checks** — the full CI suite (`ci.yml`) on the tagged commit;
   - **build** — `uv build`, `twine check`, and a check that the built version
     equals the tag;
   - **publish** — pauses on the `pypi` environment;
   - **github-release** — after PyPI accepts the upload, creates the GitHub
     Release `vX.Y.Z` with the wheel and sdist attached.
4. **Approve the deployment** (the one manual step): the run page shows
   *"Review pending deployments"* → tick `pypi` → *Approve and deploy*.
5. Verify: <https://pypi.org/project/fredq/> shows the new version and the
   GitHub Release exists.

Release notes come from `docs/release_vX.Y.Z.md` when it exists, otherwise from
the `## [X.Y.Z]` section of `CHANGELOG.md`, otherwise from GitHub's generated
notes (with a warning on the run). If a release for the tag already exists, the
distribution files are uploaded to it instead.

If a step fails before publishing (a red check, a version mismatch), fix it on
`main`, delete the tag (`git push origin :refs/tags/vX.Y.Z`, then
`git tag -d vX.Y.Z`) and tag again. If only a later step failed, use *Re-run
failed jobs* on the run. A version that reached PyPI can never be uploaded
again: release the fix as the next patch version.

## Verify locally before releasing

```bash
uv build
uvx twine check dist/*
```

The built filenames carry the version `hatch-vcs` derived from git
(`fredq-X.Y.Z...`). A clean checkout *at* the tag yields exactly `X.Y.Z`; a dirty
tree or post-tag commit yields a `.devN`/`+g<sha>` suffix.
