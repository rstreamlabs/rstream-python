# rstream Python SDK

`rstreamlabs-rstream` is the Python SDK for rstream tunnels and webhook
receivers. Python code imports it as `rstream`.

The SDK is async-first, framework-neutral, and uses the same runtime protocol
and CLI-compatible configuration model as the Go, JavaScript, Java, and C++
SDKs. It is designed for Python services that need to publish local HTTP
applications, dial private tunnels, accept bytestream tunnel connections
directly, or verify rstream webhook deliveries in a backend framework.

## SDK Surface

This repository targets Python 3.10 and newer.

The first public release focuses on the Python-native surface that is ready for
production use:

| Area | Supported |
| --- | --- |
| Runtime client | Async control-channel client |
| Published tunnels | HTTP/1.1 bytestream tunnels |
| Private tunnels | Dial by tunnel name or ID |
| Local forwarding | `BytestreamTunnel.forward_to(host, port)` |
| Direct accept | `await tunnel.accept()` and async iteration |
| ASGI helper | Direct HTTP/1.1 bridge for ASGI apps |
| WSGI helper | Direct HTTP/1.1 bridge for WSGI apps |
| Webhooks | Signature generation, verification, and event parsing |
| Config | CLI-compatible YAML config and environment variables |

Datagram tunnels, QUIC runtime transport, HTTP/3 tunnel creation, custom
transport proxies, and external credential stores are rejected explicitly by
this SDK version instead of being ignored.

## Install

```bash
pip install rstreamlabs-rstream
```

For ASGI/FastAPI helpers:

```bash
pip install "rstreamlabs-rstream[asgi]"
```

For WSGI/Flask/Django helpers:

```bash
pip install "rstreamlabs-rstream[wsgi]"
```

For managed project endpoint discovery through the Control plane API:

```bash
pip install "rstreamlabs-rstream[api]"
```

For local example applications:

```bash
pip install "rstreamlabs-rstream[examples]"
```

## Configuration

The SDK reads the same config file as the CLI by default:

```text
~/.rstream/config.yaml
```

Configuration is resolved in this order:

1. Explicit `Client(...)` options.
2. Environment variables.
3. The selected context in the config file.
4. SDK defaults.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `RSTREAM_CONFIG` | Override the config file path. |
| `RSTREAM_CONTEXT` | Select a context from the config file. |
| `RSTREAM_ENGINE` | Use an explicit engine host and optional port. |
| `RSTREAM_AUTHENTICATION_TOKEN` | Use an explicit authentication token. |
| `RSTREAM_MTLS_CERT_FILE` | Client certificate file for mTLS authentication. |
| `RSTREAM_MTLS_KEY_FILE` | Client private key file for mTLS authentication. |
| `RSTREAM_API_URL` | Control plane API URL for managed project discovery. |

`RSTREAM_ENGINE_ADDRESS` is also accepted for compatibility with older local
SDK workflows. Prefer `RSTREAM_ENGINE` in new code.

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for supported YAML fields and
error behavior.

## FastAPI tunnel

```python
import asyncio

from fastapi import FastAPI

import rstream

app = FastAPI()


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}


async def main() -> None:
    async with (
        rstream.Client.from_env() as client,
        await client.connect() as control,
    ):
        tunnel = await control.create_tunnel(
            protocol="http",
            http_version="http/1.1",
            publish=True,
        )
        print("Forwarding address:", tunnel.forwarding_address)
        await rstream.asgi.serve(app, tunnel)


asyncio.run(main())
```

The ASGI helper parses accepted rstream streams and dispatches them to the app
in-process. It does not start a loopback server.

## Local forwarding

`forward_to()` remains available for existing services that already listen on a
local TCP port:

```python
await tunnel.forward_to("127.0.0.1", 8000)
```

It keeps accepting rstream streams and relays them to the local TCP service
until the tunnel or control channel is closed.

## Private dial

```python
import asyncio

import rstream


async def main() -> None:
    async with (
        rstream.Client.from_env() as client,
        await client.dial("private-api") as stream,
    ):
        stream.write(b"ping")
        await stream.drain()
        print(await stream.read(1024))


asyncio.run(main())
```

Private tunnels are addressed by name or ID. They do not expose a public
forwarding address.

## Webhook receiver

```python
from fastapi import Request

import rstream


async def handle_webhook(request: Request) -> None:
    payload = await request.body()
    signature = request.headers["rstream-signature"]
    secret = "whsec_..."

    event = rstream.verify_event(payload, signature, secret)
    resource_id = event.object.get("id")
    if event.type == "tunnel.created":
        print("Tunnel is online:", resource_id)
```

`event.id` is suitable for idempotency. Keep the raw request body unchanged when
verifying the signature.

See [docs/WEBHOOKS.md](docs/WEBHOOKS.md) for the payload shape and headers.

## Examples

| Example | Purpose |
| --- | --- |
| [examples/forward-local-port](examples/forward-local-port) | Publish an existing local TCP service. |
| [examples/private-dial](examples/private-dial) | Dial a private tunnel by name or ID. |
| [examples/fastapi-tunnel](examples/fastapi-tunnel) | Publish a FastAPI app through the direct ASGI helper. |
| [examples/flask-tunnel](examples/flask-tunnel) | Publish a Flask app through the direct WSGI helper. |
| [examples/django-tunnel](examples/django-tunnel) | Publish a Django app through the direct WSGI helper. |
| [examples/aiohttp-local-forwarding](examples/aiohttp-local-forwarding) | Publish an aiohttp app through managed local forwarding. |
| [examples/webhook-receiver](examples/webhook-receiver) | Verify webhook deliveries inside a FastAPI route. |
| [examples/flask-webhook-receiver](examples/flask-webhook-receiver) | Verify webhook deliveries inside a Flask route. |
| [examples/django-webhook-receiver](examples/django-webhook-receiver) | Verify webhook deliveries inside a Django view. |

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy
pytest
python -m build
```

Real-engine tests are opt-in:

```bash
RSTREAM_PYTHON_E2E=1 pytest tests/e2e
```

See [docs/TESTING.md](docs/TESTING.md) for local-engine and managed-environment
test commands.

## Repository setup and release

The intended GitHub repository is `rstreamlabs/rstream-python`. CI requires no
secret for normal pull request checks. Release automation uses release-please and
requires the maintainer-managed `RELEASE_PLEASE_TOKEN` secret plus the
`CI_ALLOWED_ACTOR` repository variable.

See [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md) before creating or publishing
the repository.

## License

Apache-2.0. See [LICENSE](LICENSE).
