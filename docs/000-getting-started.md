# Run a first Python application

Use the published package for a new application. Use a checkout to run the
complete framework examples or test changes to the SDK. Both paths need
Python 3.10 or newer. A tunnel also needs a project or direct Engine that
allows the operation.

## Install the package

Create a virtual environment in your application directory.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install "rstreamlabs-rstream[asgi,api]" fastapi
```

On Windows PowerShell, create the environment with `py -m venv .venv`.
Activate it with `.\.venv\Scripts\Activate.ps1` and use the same
`python -m pip install` command. Import the package as `rstream`. The
`asgi` extra supplies the HTTP adapter and `api` supplies managed project
discovery. With a configured direct Engine, the ASGI adapter works with
the `asgi` extra alone.

## Run and verify the FastAPI application

For hosted rstream, [install the CLI](https://rstream.io/docs/getting-started/installation)
and use a project that permits HTTP publication. Sign in with the CLI.

```sh
rstream login
```

List your projects.

```sh
rstream project list
```

Replace `my-project-endpoint` with the value from the `ENDPOINT` column.

```sh
rstream project use my-project-endpoint
```

For a self-hosted Engine, use an [Engine context](001-configuration.md). The
SDK uses the system trust store by default. If the Engine uses a private
CA, set `SSL_CERT_FILE` to the CA bundle before starting Python.

```sh
export SSL_CERT_FILE=/path/to/ca-bundle.pem
```

In PowerShell, set `$env:SSL_CERT_FILE = 'C:\path\to\ca-bundle.pem'`.
Unattended services can use a provisioned identity.

Save the following program as `main.py`.

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

Start the application from that directory.

```sh
python main.py
```

Wait for `Forwarding address:`. Request that HTTPS address and expect
HTTP 200 with `{"status":"ok"}`. Use the
[required caller credential](https://rstream.io/docs/tunnels/http-tunnels/authentication)
when the project protects the endpoint. With a private CA, configure your
HTTP client to trust it and keep the printed hostname for verification.
Stop the program with Ctrl+C.

## Build and test the checkout

Clone the repository. Create and activate an environment as above. From
the repository root, install the editable SDK and example dependencies.

```sh
git clone https://github.com/rstreamlabs/rstream-python.git
cd rstream-python
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[examples,asgi,wsgi,api]"
python examples/fastapi-tunnel/main.py
```

The last command uses the SDK from `src/rstream` and the selected context.
The [example catalog](../examples/README.md) has equivalent Flask, Django
and local forwarding paths. To build a wheel and run the SDK's local tests,
follow [Contributing](../CONTRIBUTING.md#local-setup).
