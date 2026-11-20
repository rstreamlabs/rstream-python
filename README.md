# rstream Python SDK

rstream connects services and devices through outbound connections, so they can be reached without opening inbound ports on their hosts. This SDK embeds that connection in a Python application, without a separate agent process.

Its async API fits `asyncio` services and workers. ASGI and WSGI adapters serve an existing web application directly over accepted tunnel streams; the same SDK can dial private services and verify webhook deliveries.

The package is named `rstreamlabs-rstream`; import it as `rstream`. Python 3.10 or newer is required.

## Where this SDK fits

An rstream agent connects outbound to the edge, which routes traffic to the application and applies project and tunnel policy. Published tunnels provide a forwarding address; private tunnels are reached by name or ID through an authenticated rstream client.

| Integration | Python support |
| --- | --- |
| Application servers | Serve HTTP/1.1 through ASGI, WSGI or accepted bytestreams. |
| Existing services | Forward tunnel connections to a local TCP port. |
| Private connectivity | Dial bytestream tunnels by name or ID. |
| Service discovery | Query inventory and watch lifecycle events with optional HTTP dependencies. |
| Webhooks | Verify signatures and parse deliveries in your framework. |

The runtime connects to the engine over TLS. Datagram tunnels, QUIC runtime transport and HTTP/3 tunnel creation are outside this SDK’s current scope. The [SDK guide](https://rstream.io/sdks) compares the available language and protocol choices.

## Publish a FastAPI application

[Install the package and select a project](https://github.com/rstreamlabs/rstream-python/blob/main/docs/000-getting-started.md).
This application owns FastAPI startup and shutdown and serves requests
directly over the tunnel.

```python
import asyncio
from contextlib import suppress

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
        print("Forwarding address:", tunnel.forwarding_address, flush=True)
        await rstream.asgi.serve(app, tunnel)


with suppress(KeyboardInterrupt):
    asyncio.run(main())
```

Run `python main.py` and open the forwarding address to receive
`{"status":"ok"}`. The [first-application guide](https://github.com/rstreamlabs/rstream-python/blob/main/docs/000-getting-started.md)
explains how to verify the endpoint and build the checkout.

## Documentation

| Task | Guide |
| --- | --- |
| Install the SDK or build the checkout | [Getting started](https://github.com/rstreamlabs/rstream-python/blob/main/docs/000-getting-started.md) |
| Serve an application or forward an existing port | [Choose a tunnel integration](https://github.com/rstreamlabs/rstream-python/blob/main/docs/002-tunnels.md) |
| Find an equivalent Flask, Django or asyncio example | [Example catalog](https://github.com/rstreamlabs/rstream-python/blob/main/examples/README.md) |
| Configure credentials or verify a webhook | [Documentation index](https://github.com/rstreamlabs/rstream-python/blob/main/docs/README.md) |
| Develop the SDK | [Contributing](https://github.com/rstreamlabs/rstream-python/blob/main/CONTRIBUTING.md) |

## Security and support

Use [Security](SECURITY.md) to report vulnerabilities privately. Usage questions and reproducible bugs belong in [GitHub issues](https://github.com/rstreamlabs/rstream-python/issues); remove credentials and customer identifiers before sharing a reproduction. Licensed under [Apache-2.0](LICENSE).
