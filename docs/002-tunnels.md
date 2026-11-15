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
        app.router.lifespan_context(app),
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

### Own the application lifecycle

The helper serves **HTTP/1.1 requests only**. It does not dispatch ASGI `lifespan`
or WebSocket scopes. In the FastAPI example, the outer
`app.router.lifespan_context(app)` starts the application's lifespan before
connecting and stops it after tunnel/client cleanup, including setup errors and
cancellation. Put process resources on `app.state`; the adapter does not populate
ASGI lifespan `scope["state"]` from a yielded state mapping. Nested subapplication
lifespans remain the application's responsibility.

For an application that needs WebSockets, another ASGI server feature, or a
framework with a different lifecycle, keep its normal server and use
[`forward_to()`](#managed-local-forwarding). For example, run Uvicorn on loopback
in one terminal and the forward-local-port example in another. The full server
then owns ASGI startup, shutdown and WebSocket handling; the SDK owns the tunnel.

| Direct adapter option | Default | Use it for |
| --- | --- | --- |
| `max_header_size` | 65536 bytes | Bound an incomplete request-header block. |
| `max_body_size` | 16777216 bytes | Bound request bodies; WSGI buffers its input. |
| `read_timeout` | 30 seconds | Bound each request read; `None` disables this local read timeout. |

These are arguments to `rstream.asgi.serve` or `rstream.wsgi.serve`, separate from
client connection/operation timeouts and from framework policy.

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

Install `rstreamlabs-rstream[api]` for this inventory/SSE path; use the
`realtime` extra when selecting WebSocket watches.

```python
async with rstream.Client.from_env() as client:
    filters = rstream.TunnelFilters(labels={"role": "inference"})
    workers = await client.list_tunnels(filters=filters)
    async with client.watch(tunnels=filters) as events:
        async for event in events:
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

The low-level client does not recreate control channels or tunnels automatically.
When a serving operation ends, the application decides whether to stop or create a
new client/control/tunnel with bounded backoff. Keep that supervision outside the
request handler. Preserve a requested hostname across attempts when a consumer
needs the same public address, and do not replay application requests on recovery.
Explicit close/cancellation must stop the supervisor as well as its current
resources. The [vision application](https://github.com/rstreamlabs/rstream-examples/tree/main/python-vision-inference)
shows an application-owned reconnect loop.

## Creation options

`control.create_tunnel` accepts keyword arguments or `CreateTunnelOptions`.
Unset optional fields are sent as unspecified and the Engine validates their
combination and project permissions. Set `publish` explicitly in applications.
Do not treat inventory-only `id`, `host` or `creation_date` as creation inputs.

| Options | Purpose and boundary |
| --- | --- |
| `name`, `labels` | Dialing/discovery identity and application metadata. A name is not a stable public hostname. |
| `publish`, `type`, `protocol` | Public entrypoint or private dial; this SDK implements bytestreams. Protocol availability still depends on the Engine/project. |
| `hostname`, `port` | Request a stable domain for eligible published protocols, or a previously reserved TCP port. Neither reserves a domain/port by itself. |
| `http_version`, `upstream_tls` | HTTP upstream mode. Use `http/1.1` for these direct adapters; a local h2c service can use forwarding. Explicit HTTP version and upstream TLS cannot conflict. HTTP/3 is rejected. |
| `token_auth`, `rstream_auth`, `challenge_mode` | Published HTTP request policy at the edge; independent of agent authentication. `auth=TunnelAuth(...)` is the grouped spelling. |
| `http_cors` | Explicit published HTTP browser-origin policy; see below. |
| `tls_mode`, `tls_min_version`, `tls_alpns`, `tls_ciphers`, `mtls_auth` | Published TLS termination/passthrough and downstream certificate policy. Passthrough leaves TLS policy to the application. |
| `trusted_ips`, `geo_ip` | Published source-address/country restrictions, enforced by the Engine. |
| `allow_cross_region_routing` | Override the project's private-routing choice where supported; not a region selector for the client. |

Private tunnels reject public exposure/authentication options. Private protocol
inspection options are supported where the Engine accepts them; an opaque private
HTTP byte stream does not require a protocol declaration.

## HTTP CORS

Pass `http_cors=HTTPCORS(allowed_origins=("https://dashboard.example",), allowed_methods=("GET", "PUT"), allowed_headers=("Authorization",), exposed_headers=("ETag",), max_age=600)` to `create_tunnel` or `CreateTunnelOptions`. Import `HTTPCORS` from `rstream`.

CORS requires a published HTTP tunnel. Allowed origins must be explicit HTTP(S) origins without paths or wildcards. Omitted method and request-header lists use GET/HEAD/POST and Authorization/Content-Type; credentials are disabled and max age is zero by default. An absent policy preserves upstream CORS. Engine answers valid preflights before request authentication, but every actual request still requires its usual authorization. A preflight does not grant access to the upstream application.

## Find the next API

| Surface | Purpose and owner |
| --- | --- |
| `Client.connect`, `dial` / `dial_bytestream` | Open a control or private stream; use async contexts and stream EOF/errors. |
| `ControlChannel.create_tunnel`, `close`, `done` | Admit tunnels and observe control liveness. `done` does not establish payload completion. |
| `BytestreamTunnel.accept`, async iteration, `forward_to`, `close` | Own accepted streams, or have the SDK relay them to a local TCP service. |
| `Client.list_clients`, `list_tunnels`, `watch` | Optional Engine HTTP inventory and event stream. Keep watches in `async with` or call `aclose` when leaving early. |
| `Client.generate_stable_hostname` | Derive a managed hostname once and retain it across supervised reconnects. |
| `rstream.verify_event`, signing/header helpers | Verify receiver bytes or produce synthetic local webhook deliveries; not Control plane administration. |

Exact signatures are in [client.py](../src/rstream/client.py),
[tunnel.py](../src/rstream/tunnel.py), and [types.py](../src/rstream/types.py).
The core SDK remains framework-neutral; optional extras add integration protocols.
