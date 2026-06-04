# Tunnels

The runtime client is async-first and uses the same engine protocol as the Go,
JavaScript, and C++ SDKs.

## Serve ASGI directly

Install the optional ASGI extra:

```bash
pip install "rstreamlabs-rstream[asgi]"
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

Install the optional WSGI extra:

```bash
pip install "rstreamlabs-rstream[wsgi]"
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
