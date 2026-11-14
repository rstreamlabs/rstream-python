# Tunnels

The runtime client is async-first and uses the same engine protocol as the Go,
JavaScript, and C++ SDKs.

## Serve ASGI directly

Install the ASGI extra and the framework used by this example:

```bash
pip install "rstreamlabs-rstream[asgi]" fastapi
```

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
        print(tunnel.forwarding_address)
        await rstream.asgi.serve(app, tunnel)


asyncio.run(main())
```

The ASGI helper parses accepted rstream streams and dispatches them to the
application in-process. Request bodies are streamed through the ASGI `receive`
callable and bounded by default request limits. It does not start a loopback
HTTP server.

## Serve WSGI directly

Install the WSGI extra and Flask for this example:

```bash
pip install "rstreamlabs-rstream[wsgi]" flask
```

```python
import asyncio

from flask import Flask, jsonify

import rstream

app = Flask(__name__)


@app.get("/")
def root() -> object:
    return jsonify(status="ok")


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
        print(tunnel.forwarding_address)
        await rstream.wsgi.serve(app, tunnel)


asyncio.run(main())
```

The WSGI helper follows the same stream-native model for Flask, Django, and
other WSGI applications. WSGI applications receive a buffered `wsgi.input`
body, so use the `max_body_size` option when accepting large or untrusted
requests.

## Dial a private tunnel

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

## Managed local forwarding

Services that already expose a local TCP socket can use managed forwarding. The
aiohttp local-forwarding example starts the application on loopback, opens a
published rstream tunnel, then forwards accepted tunnel streams to that port:

```python
async with (
    rstream.Client.from_env() as client,
    await client.connect() as control,
):
    tunnel = await control.create_tunnel(
        protocol="http",
        http_version="http/1.1",
        publish=True,
    )
    await tunnel.forward_to("127.0.0.1", local_port)
```

See [examples/aiohttp-local-forwarding](../examples/aiohttp-local-forwarding)
for a runnable version.

## Published TCP tunnels

Set `protocol="tcp"` for a published raw TCP bytestream. Leave `port` unset for an ephemeral address, or set it to a port already reserved by the project through the Control plane:

```python
async with (
    rstream.Client.from_env() as client,
    await client.connect() as control,
):
    tunnel = await control.create_tunnel(
        protocol="tcp",
        publish=True,
        port=10042,
    )
    print(tunnel.forwarding_address)
    await tunnel.forward_to("127.0.0.1", 22)
```

The SDK does not reserve the port. A TCP tunnel forwards the downstream connection without adding encryption or authentication, so use a secure application protocol such as SSH. Use a TLS tunnel for TLS traffic.

## Discover tunnels and watch events

Tunnels carry labels, and the engine inventory is queryable and watchable from
the same client. This turns the tunnel registry into a service registry: tag
tunnels at creation time, discover them by label, and react to lifecycle
events in real time.

```python
async with rstream.Client.from_env() as client:
    filters = rstream.TunnelFilters(labels={"role": "inference"})
    workers = await client.list_tunnels(filters=filters)
    async for event in client.watch(tunnels=filters):
        if event.type in ("tunnel.created", "tunnel.deleted"):
            ...  # refresh the worker set
```

`list_tunnels` returns `TunnelInventory` entries combining the tunnel
properties with the live `status` and owning `client_id`. `watch` defaults to
SSE and switches to WebSocket with `transport="websocket"`. Listing and SSE
require the `api` extra; WebSocket requires the `realtime` extra.

## Stable viewer domains

A published tunnel created without a hostname is given a fresh engine endpoint
each time. To keep a constant address across reconnects, generate a stable
project-scoped domain once and pass it on every `create_tunnel`:

```python
async with rstream.Client.from_env() as client:
    hostname = await client.generate_stable_hostname()
    async with await client.connect() as control:
        tunnel = await control.create_tunnel(
            protocol="http",
            http_version="http/1.1",
            publish=True,
            hostname=hostname,
        )
```

The address has the form `<slug>-<project-endpoint>.t.<cluster-domain>`,
matching the Go and C++ SDKs. Generating it once and reusing it is what makes
it stable; the method returns `None` for engines that are not managed project
hosts, in which case the engine allocates an address. The pure derivation is
`rstream.generate_stable_domain(engine)`.

## Connection lifecycle

The control channel uses a negotiated heartbeat deadline. If that deadline
expires, or the control transport ends unexpectedly, the SDK immediately stops
accepting new streams but lets already accepted streams and active
`forward_to()` relays drain normally. This avoids interrupting an established
application session because of a transient or asymmetric control-path outage.
An explicit tunnel/control close or a protocol violation remains a hard close
and terminates active local forwarding. Applications should use each stream's
EOF/error as its payload-lifecycle signal; `control.done()` only describes the
control plane.

## HTTP CORS

Pass `http_cors=HTTPCORS(allowed_origins=("https://dashboard.example",), allowed_methods=("GET", "PUT"), allowed_headers=("Authorization",), exposed_headers=("ETag",), max_age=600)` to `create_tunnel` or `CreateTunnelOptions`. Import `HTTPCORS` from `rstream`.

CORS requires a published HTTP tunnel. Allowed origins must be explicit HTTP(S) origins without paths or wildcards. Omitted method and request-header lists use GET/HEAD/POST and Authorization/Content-Type; credentials are disabled and max age is zero by default. An absent policy preserves upstream CORS. Engine answers valid preflights before request authentication, but every actual request still requires its usual authorization. A preflight does not grant access to the upstream application.
