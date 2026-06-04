# Contributing

Thanks for considering a contribution to `rstream-python`.

## Before opening a change

Small fixes can be proposed directly. For public API changes, runtime protocol
changes, configuration semantics, or new tunnel capabilities, open an issue or
discussion first so the SDK behavior can stay aligned with the Go, JavaScript,
Java, and C++ SDKs.

## Local setup

Use Python 3.10 or newer:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Development checks

Run the full local suite before opening a pull request:

```bash
ruff check .
ruff format --check .
mypy
pytest
python -m build
```

When a change affects runtime behavior, include the relevant fake-engine or
real-engine e2e command in the PR description. Public pull requests do not run
maintainer-only release workflows.

## Style

Keep changes small, explicit, and idiomatic Python.

- Follow [CODING_STYLE.md](./CODING_STYLE.md).
- Keep the core SDK framework-neutral.
- Prefer typed dataclasses, narrow protocols, and explicit exceptions.
- Do not use broad `Any` typing.
- Do not silently ignore unsupported rstream features; raise an explicit SDK
  error.
- Update examples and docs with every user-facing behavior change.

## Tests

Use the smallest test that exercises the behavior:

- unit tests for config parsing, validation, webhook parsing, protocol
  conversion, and local helpers;
- fake-engine integration tests for runtime control-channel and stream behavior;
- framework example tests when changing sample integrations;
- opt-in e2e tests for real engines and managed environments.

See [docs/TESTING.md](docs/TESTING.md) for the e2e matrix.

## Generated code

The protobuf runtime files under `src/rstream/_proto` are generated from
`proto/rstream.proto`. Do not edit generated protobuf code by hand unless the
change is a temporary local investigation that will not be committed.

## Security

Do not disclose vulnerabilities in public issues. See [SECURITY.md](SECURITY.md)
for the reporting guidance used by this repository.
