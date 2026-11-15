# Configure repository CI and releases

This is a maintainer guide for `rstreamlabs/rstream-python`, not an application
installation step. Applications use the published `rstreamlabs-rstream` package;
contributors start with [Contributing](../CONTRIBUTING.md).

## CI contract

The configured CI matrix uses Python 3.10–3.15 on Linux, macOS and Windows. It
runs Ruff, strict Mypy and the local pytest suite without a rstream account.
A separate Python 3.13 job builds distributions and runs
`scripts/verify_distribution.py`. Real-engine checks remain opt-in as described
in [Testing](004-testing.md).

Protect `main` with reviewed pull requests and required CI, and restrict force
push/deletion. Normal source validation does not authorize a release.

## Release configuration

| Setting | Purpose |
| --- | --- |
| Repository variable `CI_ALLOWED_ACTOR` | Actor allowed to run release-please, candidate and promotion jobs. |
| Repository secret `RELEASE_PLEASE_TOKEN` | Minimum required contents/PR authority for release-please. |
| GitHub environment `pypi` | Protect stable promotion with the repository's maintainer approval policy. |
| PyPI trusted publisher | Owner `rstreamlabs`, repository `rstream-python`, workflow `publish.yml`, environment `pypi`, project `rstreamlabs-rstream`. |

The existing promotion workflow requests `id-token: write` and uses PyPI trusted
publishing; it does not need a long-lived PyPI API token. Configure the publisher
and protected environment before attempting promotion. Do not replace this with
an ambient personal token as a quick-start workaround.

Keep `release-please-config.json` and `.release-please-manifest.json` versioned.
Release-please coordinates the Python package version, runtime version file,
changelog, tag and draft GitHub release.

## Candidate and stable promotion

| Workflow | Input and result |
| --- | --- |
| `release-please.yml` | An allowed push on `main` prepares the release PR/draft and tag. |
| `release-candidate.yml` | A `vX.Y.Z` tag verifies the version, builds wheel/sdist, validates them and retains a checksummed candidate for 90 days. It does not publish PyPI. |
| `publish.yml` | Explicit `release_tag` dispatch selects the successful candidate with the matching tag commit, checks integrity and PyPI state, publishes those retained bytes and then the GitHub release. It never rebuilds the candidate. |

Promotion requires the GitHub release to remain a draft and refuses an older
release after a newer stable version. Existing PyPI files must match the retained
candidate; retries use that same artifact, not a new build with the same version.
Review the workflow and verification scripts when changing this contract.

Before proposing a release, run the contributor checks, distribution verification
and relevant explicit real-engine matrix; retain the commands, environment and
results privately. An unrun opt-in test is not a passed qualification. Candidate
creation, publishing and repository-visibility changes are separate maintainer
operations and are not side effects of an ordinary build.
