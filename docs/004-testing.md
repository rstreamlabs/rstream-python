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
| `tests/integration` | TLS fake engine, control-channel lifecycle, tunnel creation and close, stream handshakes, the SDK `zero_rtt` option, proxy delivery, timeout and retry behavior. |
| `tests/examples` | Syntax compilation for every example plus FastAPI, Flask, and Django receivers with valid and invalid webhook signatures. |

## Real-engine e2e

Real-engine tests are opt-in:

```bash
RSTREAM_PYTHON_E2E=1 pytest tests/e2e
```

The private-tunnel e2e matrix creates a tunnel, dials it by name and ID, runs
the SDK stream-handshake `zero_rtt` option both enabled and disabled, exercises concurrent dials, and validates a
direct WSGI handler through a private tunnel.

Published HTTP tunnel checks are opt-in because they require the engine to serve
published hosts. They cover both managed local forwarding and direct ASGI
serving:

```bash
RSTREAM_PYTHON_E2E=1 \
RSTREAM_PYTHON_E2E_PUBLISHED=1 \
pytest tests/e2e
```

Published TCP checks have a separate opt-in because the project and engine must
allow published TCP tunnels and the allocated port must be reachable:

```bash
RSTREAM_PYTHON_E2E=1 \
RSTREAM_PYTHON_E2E_PUBLISHED_TCP=1 \
pytest tests/e2e
```

Set `RSTREAM_PYTHON_E2E_PUBLISHED_CONNECT_HOST` when the hostname returned by a
local engine is not directly resolvable from the test process.

When bypassing the shared rstream config file, pass explicit engine settings.
For a private CA, keep certificate verification enabled:

```bash
RSTREAM_PYTHON_E2E=1 \
RSTREAM_PYTHON_E2E_ENGINE="c.localhost.rstream.io:9443" \
RSTREAM_PYTHON_E2E_TOKEN="$RSTREAM_AUTHENTICATION_TOKEN" \
RSTREAM_PYTHON_E2E_CA_FILE="/path/to/local-ca.pem" \
pytest tests/e2e
```

Set `RSTREAM_PYTHON_E2E_SERVER_NAME` only when the certificate name intentionally
differs from the engine host. `RSTREAM_PYTHON_E2E_TLS_INSECURE=1` disables
certificate verification and is reserved for isolated throwaway fixtures
without a trusted certificate.

The `zero_rtt` option tested here controls the rstream stream handshake; it does
not enable TLS 1.3 early data.

## Local self-hosted engine

Follow the [self-hosted engine guide](https://rstream.io/docs/tunnels/self-hosted)
to configure a local engine, select its CLI context and run:

```bash
RSTREAM_CONTEXT=tests \
RSTREAM_PYTHON_E2E=1 \
RSTREAM_PYTHON_E2E_PUBLISHED=1 \
RSTREAM_PYTHON_E2E_PUBLISHED_TCP=1 \
pytest tests/e2e
```

Enable published checks only when the local engine supports them and its
forwarding addresses are reachable from the test process.
