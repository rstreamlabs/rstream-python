# Choose a Python tunnel integration

A published tunnel has a forwarding address for ordinary clients. A
private tunnel is reached by name or ID through an authenticated rstream
client. The Python SDK connects to the Engine over TLS and carries byte
streams. Check [edition and protocol availability](https://rstream.io/docs/sdks)
before choosing a public entrypoint.

| I need to | Use |
| --- | --- |
| Serve HTTP directly from FastAPI, Flask or Django | The [ASGI or WSGI adapter](tunnels/000-http-applications.md#serve-fastapi-flask-or-django-in-process). |
| Keep an application server, its WebSocket handling or its worker setup | [Local forwarding](tunnels/000-http-applications.md#keep-an-existing-application-server). |
| Reach a private service or forward raw TCP | The [private and TCP walkthrough](tunnels/001-private-and-tcp.md). |
| Find services and respond to changes | [Inventory and watches](tunnels/003-inventory.md). |

Use [Getting started](000-getting-started.md) to install and select a context.

## Serve ASGI directly

`rstream.asgi.serve(app, tunnel)` applies framework routing and middleware
to HTTP/1.1 requests. Follow the [FastAPI walkthrough](tunnels/000-http-applications.md)
to start it and send a request.

### Own the application lifecycle

Start the framework's lifespan before admitting traffic. The adapter
delivers HTTP scopes. Use [the lifecycle walkthrough](tunnels/000-http-applications.md#serve-fastapi-flask-or-django-in-process)
to see how FastAPI resources stay alive until tunnel work stops.

## Serve WSGI directly

Use `rstream.wsgi.serve(app, tunnel)` for synchronous Flask and Django
applications. The [same walkthrough](tunnels/000-http-applications.md#serve-fastapi-flask-or-django-in-process)
shows how to run them and set read and body limits.

## Dial a private tunnel

The [private example](tunnels/001-private-and-tcp.md#dial-a-private-http-service)
starts an owner and proves that a Python caller can exchange data with it.

## Managed local forwarding

Use `tunnel.forward_to(host, port)` when an application already listens.
The [local HTTP walkthrough](tunnels/000-http-applications.md#keep-an-existing-application-server)
runs Uvicorn and the forwarder in separate terminals.

## Published TCP tunnels

Use the [TCP walkthrough](tunnels/001-private-and-tcp.md#publish-a-tcp-service)
for the ephemeral port, reservation and application-security choices.

## Discover tunnels and watch events

See [list and watch live tunnels](tunnels/003-inventory.md) for a runnable
list and a bounded workflow for observing a tunnel as it starts and stops.

## Stable viewer domains

[Reuse a stable hostname](tunnels/002-lifecycle.md) if the service should
keep the same public address across restarts.

## Connection lifecycle

[Own the tunnel lifecycle](tunnels/002-lifecycle.md) explains the separate
lifetimes of a control channel, a tunnel and its streams.

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
| `allow_cross_region_routing` | Override the cross-region routing policy for an eligible published or private tunnel. Select the client's region separately. |

Private tunnels reject public exposure/authentication options. Private protocol
inspection options are supported where the Engine accepts them; an opaque private
HTTP byte stream does not require a protocol declaration.

## HTTP CORS

Pass `http_cors=HTTPCORS(allowed_origins=("https://dashboard.example",), allowed_methods=("GET", "PUT"), allowed_headers=("Authorization",), exposed_headers=("ETag",), max_age=600)` to `create_tunnel` or `CreateTunnelOptions`. Import `HTTPCORS` from `rstream`.

CORS requires a published HTTP tunnel. Allowed origins must be explicit HTTP(S) origins without paths or wildcards. Omitted method and request-header lists use GET/HEAD/POST and Authorization/Content-Type; credentials are disabled and max age is zero by default. An absent policy preserves upstream CORS. Engine answers valid preflights before request authentication, but every actual request still requires its usual authorization. A preflight does not grant access to the upstream application.

## Find the next API

The implementation exposes the exact call signatures in
[`client.py`](../src/rstream/client.py), [`tunnel.py`](../src/rstream/tunnel.py)
and [`types.py`](../src/rstream/types.py). Use the
[example catalog](../examples/README.md) for complete programs.
