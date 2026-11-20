# Serve a Python web application

The SDK can dispatch requests to an ASGI or WSGI application over accepted
tunnel streams. If the application already runs in an HTTP server, a
forwarder can leave routing, startup and protocol handling with that server.

## Serve FastAPI, Flask or Django in-process

Use the [source installation](../000-getting-started.md#build-and-test-the-checkout)
and select a context that can publish HTTP. Each program starts an HTTP/1.1
tunnel and attaches a framework application. Run one from the checkout root.

| Framework | Adapter | Command | Response at the forwarding address |
| --- | --- | --- | --- |
| FastAPI | `rstream.asgi.serve` | `python examples/fastapi-tunnel/main.py` | JSON with `status` set to `ok`. |
| Flask | `rstream.wsgi.serve` | `python examples/flask-tunnel/main.py` | JSON with `framework` set to `flask` and `ok` set to `true`. |
| Django | `rstream.wsgi.serve` | `python examples/django-tunnel/main.py` | JSON with `framework` set to `django` and `ok` set to `true`. |

Open the printed `Forwarding address:`, using the authentication and trust
expected by the project. Stop the program with Ctrl+C. No loopback server
needs to be started for these examples.

The ASGI adapter delivers HTTP request chunks through `receive`. It handles
HTTP scopes. FastAPI startup and shutdown belong to the calling program.
The [FastAPI example](../../examples/fastapi-tunnel/main.py) uses
`app.router.lifespan_context(app)` around the SDK's async contexts. This
makes application resources available before admitting requests and
releases them after tunnel work stops. Store resources used by the
adapter on `app.state`. Arrange nested application lifespans explicitly.

The WSGI adapter buffers the body for `wsgi.input` and invokes the synchronous
application in a worker thread. It buffers the response too. For streaming
responses or SSE, use the framework's serving stack with local forwarding.
Configure request limits and keep the
framework's own settings, such as Django's allowed hosts. Keep blocking
database or filesystem work out of the asyncio event loop.

| Setting | Default | Effect |
| --- | --- | --- |
| `max_header_size` | 64 KiB | Limits request headers. |
| `max_body_size` | 16 MiB | Limits request bodies. |
| `read_timeout` | 30 seconds | Bounds request reads. `None` disables that timeout. |

These are adapter arguments. Use the [client configuration](../001-configuration.md)
for Engine and operation timeouts.

## Keep an existing application server

Use a full application server for WebSockets, ASGI lifespan-scope state,
or server facilities such as process workers. For example, run the FastAPI
app in Uvicorn and use the SDK to forward the tunnel to it. From the checkout
root with the example dependencies installed:

```sh
python -m pip install uvicorn
python -m uvicorn --app-dir examples/fastapi-tunnel main:app --host 127.0.0.1 --port 8000
```

In another terminal with the same environment and Engine context:

```sh
python examples/forward-local-port/main.py 127.0.0.1 8000
```

Compare the JSON returned by the local address and the printed forwarding
address. Stop the forwarder and then Uvicorn. The framework and its HTTP
server own startup, request handling and shutdown. The SDK copies data
between the tunnel and the loopback socket. The
[aiohttp example](../../examples/aiohttp-local-forwarding/README.md) manages
both components in one asyncio application.
