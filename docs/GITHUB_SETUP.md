# GitHub setup

This repository is intended to be published as `rstreamlabs/rstream-python`.

## Create the repository

From the repository root:

```bash
gh repo create rstreamlabs/rstream-python \
  --private \
  --source . \
  --remote origin \
  --push
```

Keep the repository private until the first maintainer review is complete. After
validation, make it public:

```bash
gh repo edit rstreamlabs/rstream-python --visibility public
```

Recommended repository settings:

```bash
gh repo edit rstreamlabs/rstream-python \
  --enable-issues=true \
  --enable-projects=false \
  --enable-wiki=false
```

## Required CI settings

The normal CI workflow does not require secrets. It runs on pushes to `main` and
on pull requests:

- Ruff lint and format check.
- Mypy strict type check.
- Pytest.
- Source distribution and wheel build.
- Linux, macOS, and Windows.
- Python 3.10, 3.11, 3.12, and 3.13.

Release automation requires:

| Kind | Name | Purpose |
| --- | --- | --- |
| Repository variable | `CI_ALLOWED_ACTOR` | GitHub login allowed to run release-please on `main`. |
| Repository secret | `RELEASE_PLEASE_TOKEN` | Token used by release-please to create and update release PRs. |

`release-please-config.json` and `.release-please-manifest.json` are part of
the repository contract. Keep both files versioned so release-please can update
`pyproject.toml`, `src/rstream/version.py`, `CHANGELOG.md`, tags, and GitHub
releases from the same manifest state.

`RELEASE_PLEASE_TOKEN` should have the minimum permissions needed to write
contents and pull requests in this repository. The workflow is guarded by
`CI_ALLOWED_ACTOR` so regular contributors cannot trigger release automation.

## Branch protection

Before making the repository public, protect `main` with:

- pull request required before merge;
- CI required;
- no force pushes;
- no branch deletion;
- linear history if that remains consistent with the rest of the rstream SDK
  repositories.

## PyPI publishing

The package distribution name is `rstreamlabs-rstream`. The import package
inside Python remains `rstream`, so application code uses `import rstream`.

Prefer PyPI trusted publishing over a long-lived API token. Configure the PyPI
project with:

| Field | Value |
| --- | --- |
| Owner | `rstreamlabs` |
| Repository | `rstream-python` |
| Project name | `rstreamlabs-rstream` |
| Workflow | the future publish workflow filename |
| Environment | `pypi`, if an environment gate is used |

This repository currently includes CI and release-please. Add the PyPI publish
workflow only when the first public package release is approved.

If trusted publishing is not available, use a scoped `PYPI_API_TOKEN` secret, but
prefer keeping that path disabled until release policy is decided.

## First push checklist

Before the first push:

```bash
ruff check .
ruff format --check .
mypy
pytest
python -m build
```

Also run at least one real-engine e2e command from [TESTING.md](TESTING.md)
against a local or managed engine and record the command in the release notes or
PR description.
