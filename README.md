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

The runtime connects to the engine over TLS. Datagram tunnels, QUIC runtime transport and HTTP/3 tunnel creation are outside this SDK’s current scope. The [SDK guide](https://rstream.io/docs/sdks) compares the available language and protocol choices.

## Publish a FastAPI application

Use a Python virtual environment for the application:

```sh
python -m venv .venv
```

Activate it with `. .venv/bin/activate` on a POSIX shell or `.venv\Scripts\Activate.ps1` in Windows PowerShell. Then install the SDK's ASGI adapter and FastAPI:

```sh
python -m pip install "rstreamlabs-rstream[asgi]" fastapi
```

The SDK reads the [configuration](docs/001-configuration.md) selected with the [rstream CLI](https://rstream.io/docs/getting-started/installation). Install the CLI, then select a project with `rstream login` and `rstream project use my-project-endpoint`, replacing the endpoint with your own. Servers and devices can use project-scoped credentials or certificate files instead.

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
        print("Forwarding address:", tunnel.forwarding_address)
        await rstream.asgi.serve(app, tunnel)


asyncio.run(main())
```

Save this as `main.py` and run `python main.py`. Open the printed forwarding address to reach the application. The adapter handles HTTP in-process, so no local listening port is needed. The [runnable FastAPI example](examples/fastapi-tunnel) includes interrupt handling and owns FastAPI startup/shutdown explicitly. The direct adapter is HTTP-only; see its [lifecycle and scope limits](docs/002-tunnels.md#own-the-application-lifecycle) before moving an existing application.

## Documentation

| Task | Guide |
| --- | --- |
| Configure credentials, contexts and managed discovery | [Configuration](docs/001-configuration.md) |
| Forward a service, accept streams or dial privately | [Tunnels](docs/002-tunnels.md) |
| Integrate Flask, Django or another Python application | [Examples](examples/README.md) |
| Receive lifecycle notifications | [Webhooks](docs/003-webhooks.md) |
| Find advanced options or development checks | [Documentation index](docs/README.md) |
| Contribute to the SDK | [Contributing](CONTRIBUTING.md) and [coding style](CODING_STYLE.md) |

## Security and support

Use [Security](SECURITY.md) to report vulnerabilities privately. Usage questions and reproducible bugs belong in [GitHub issues](https://github.com/rstreamlabs/rstream-python/issues); remove credentials and customer identifiers before sharing a reproduction. Licensed under [Apache-2.0](LICENSE).
