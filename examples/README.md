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

Install example dependencies from the repository root:

```bash
pip install -e ".[examples]"
```
