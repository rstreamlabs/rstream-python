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

[Install the CLI](https://rstream.io/docs/getting-started/installation) and
select a hosted project that allows HTTP publication. Replace the example
endpoint with the one shown by `rstream project list`.

```sh
rstream login
rstream project list
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

Save the [README program](../README.md#publish-a-fastapi-application) as
`main.py` and run:

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
