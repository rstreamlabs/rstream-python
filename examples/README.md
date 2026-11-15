# rstream Python examples

These examples are small reference integrations for common Python service
shapes. They use the same config file and environment variables as the CLI and
the other rstream SDKs.

| Example | Purpose |
| --- | --- |
| [private-dial](private-dial) | Dial a private tunnel by name or ID. |
| [fastapi-tunnel](fastapi-tunnel) | Publish a FastAPI app through the direct ASGI helper. |
| [flask-tunnel](flask-tunnel) | Publish a Flask app through the direct WSGI helper. |
| [django-tunnel](django-tunnel) | Publish a Django app through the direct WSGI helper. |
| [forward-local-port](forward-local-port) | Publish an existing local TCP service through managed forwarding. |
| [aiohttp-local-forwarding](aiohttp-local-forwarding) | Publish an aiohttp app through managed local forwarding. |
| [webhook-receiver](webhook-receiver) | Verify webhook deliveries inside a FastAPI route. |
| [flask-webhook-receiver](flask-webhook-receiver) | Verify webhook deliveries inside a Flask route. |
| [django-webhook-receiver](django-webhook-receiver) | Verify webhook deliveries inside a Django view. |

Use Python 3.10 or newer and activate a virtual environment as described in [Contributing](../CONTRIBUTING.md). Install example dependencies from the repository root:

```bash
python -m pip install -e ".[examples]"
```

## Run a first service

[Install the CLI](https://rstream.io/docs/getting-started/installation), then run `rstream login` and `rstream project use my-project-endpoint` with your project endpoint. The first HTTP example needs permission to create a published tunnel.

From the repository root:

```sh
python examples/fastapi-tunnel/main.py
```

Open the printed forwarding address while the process is running, then stop it with an interrupt. The ASGI adapter runs the app directly over tunnel streams; it does not bind a local HTTP port. The [FastAPI guide](fastapi-tunnel) explains that example; choose a webhook receiver when the task is verifying notifications rather than serving through a tunnel.
