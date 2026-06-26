# Testing

Install development dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Run the local validation suite:

```bash
ruff check .
ruff format --check .
mypy
pytest
python -m build
```

## Local deterministic tests

The default pytest suite does not require a real engine:

```bash
pytest tests/unit tests/integration tests/examples
```

It covers:

| Suite | Coverage |
| --- | --- |
| `tests/unit` | Config resolution, protocol framing, streams, tunnel objects, API helpers, direct ASGI and WSGI helpers, webhook signatures. |
| `tests/integration` | TLS fake engine, control-channel lifecycle, tunnel creation and close, stream handshakes, zero-RTT, proxy delivery, timeout and retry behavior. |
| `tests/examples` | Syntax compilation for every example plus FastAPI, Flask, and Django receivers with valid and invalid webhook signatures. |

## Real-engine e2e

Real-engine tests are opt-in:

```bash
RSTREAM_PYTHON_E2E=1 pytest tests/e2e
```

The private-tunnel e2e matrix creates a tunnel, dials it by name and ID, runs
zero-RTT both enabled and disabled, exercises concurrent dials, and validates a
direct WSGI handler through a private tunnel.

Published HTTP tunnel checks are opt-in because they require the engine to serve
published hosts. They cover both managed local forwarding and direct ASGI
serving:

```bash
RSTREAM_PYTHON_E2E=1 \
RSTREAM_PYTHON_E2E_PUBLISHED=1 \
pytest tests/e2e
```

When bypassing the shared rstream config file, pass explicit engine settings:

```bash
RSTREAM_PYTHON_E2E_ENGINE="c.localhost.rstream.io:9443" \
RSTREAM_PYTHON_E2E_TOKEN="$RSTREAM_AUTHENTICATION_TOKEN" \
RSTREAM_PYTHON_E2E_TLS_INSECURE=1 \
pytest tests/e2e
```

If the local engine uses a private CA, prefer
`RSTREAM_PYTHON_E2E_CA_FILE="/path/to/local-ca.pem"` instead of
`RSTREAM_PYTHON_E2E_TLS_INSECURE=1`. `RSTREAM_PYTHON_E2E_SERVER_NAME` is only
needed when the certificate name intentionally differs from the engine host.

## Local EE engine

The engine repository documents the full local setup in its Enterprise Edition
runtime README:

```text
cmd/rstream-engine-ee/README.md
```

Start the EE engine, select the test context, then run:

```bash
RSTREAM_CONTEXT=tests \
RSTREAM_PYTHON_E2E=1 \
RSTREAM_PYTHON_E2E_PUBLISHED=1 \
pytest tests/e2e
```
