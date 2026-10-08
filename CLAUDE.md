# CLAUDE.md

Home Assistant custom integration (`custom_components/curing_chamber`) driving a
charcuterie curing chamber, plus a sidebar panel and a Lovelace card bundled in
`custom_components/curing_chamber/frontend/` (vanilla JS, no build step).
Distributed through HACS.

## Development

No venv is committed. Working setup:

```bash
uv venv -p 3.13
uv pip install ruff mypy pytest-homeassistant-custom-component pytest-cov
.venv/bin/python -m pytest -q
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format --check custom_components tests
.venv/bin/mypy
node --check custom_components/curing_chamber/frontend/curing-chamber-panel.js
```

CI (`.github/workflows/validate.yml`) runs the same ruff, mypy and pytest steps
with a coverage gate of 85 % on `regulation/` and `program/`. `hassfest.yml`
and `hacs.yml` validate the integration metadata. All three must be green
before merging.

Notes:
- `hass_frontend` is not installed by the test dependency, so `frontend` /
  `panel_custom` cannot be set up in tests; panel registration is tested by
  patching `async_register_panel` in `__init__.py`.
- Mypy is strict only on the pure engines (`regulation`, `program`, `batch`);
  the HA glue is a silenced followed import.
- The panel and the card use no dependency and no CDN. Keep it that way.

## Workflow

- Work on a branch (`feature/…`, `chore/…`, `release/…`), never directly on
  `main`.
- Open a PR with `gh pr create`; wait for the three CI checks; merge with a
  merge commit (`gh pr merge --merge --delete-branch`), matching the history.
- Commit only when asked. Commit messages: one summary line, then a bulleted
  body saying what changed and why.
- Keep `CHANGELOG.md` (Keep a Changelog format) up to date under
  `## [Unreleased]` in the same PR as the change. Update the README when a
  user-facing behaviour changes.

## Release process

Releases are GitHub releases on `main`. Publishing one triggers
`.github/workflows/release.yml`, which rewrites the manifest version from the
tag and attaches `curing_chamber.zip` to the release (HACS installs from it).

1. **Choose the version** (SemVer): patch for fixes and metadata, minor for new
   features, major for breaking changes.
2. **Bump and document in one commit**, usually inside the feature PR itself
   (or a dedicated `release/vX.Y.Z` branch when several PRs accumulate):
   - `custom_components/curing_chamber/manifest.json` → `"version"`
   - `pyproject.toml` → `version`
   - `CHANGELOG.md`: rename `## [Unreleased]` content to
     `## [X.Y.Z] - YYYY-MM-DD`, leave an empty `## [Unreleased]` above it, and
     update the compare links at the bottom (`[Unreleased]` → `vX.Y.Z...HEAD`,
     add `[X.Y.Z]: …/compare/vPREV...vX.Y.Z`).
3. **Open the PR, wait for CI, merge** (see Workflow).
4. **Publish the release** from an up-to-date `main`, using the changelog
   section as the notes:

   ```bash
   git checkout main && git pull
   sed -n '/^## \[X.Y.Z\]/,/^## \[/p' CHANGELOG.md | sed '1d;$d' > /tmp/notes.md
   gh release create vX.Y.Z --target main --title vX.Y.Z --notes-file /tmp/notes.md
   ```

5. **Verify**: the Release workflow succeeds and
   `gh release view vX.Y.Z --json assets` lists `curing_chamber.zip`;
   `gh release list` shows the new tag as Latest.

Do not create the tag by hand: `gh release create` creates it, and the version
in `manifest.json` must already match the tag on `main`.
