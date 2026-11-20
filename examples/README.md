# Python application examples

[Install the checkout and start the FastAPI application](../docs/000-getting-started.md#build-and-test-the-checkout)
to verify your Python environment and Engine context. Run commands from the
repository root unless an example gives a different directory. Framework
samples use the SDK in this checkout. Webhook receivers can be tested locally
with signed deliveries and need no Engine.

| Example | Purpose |
| --- | --- |
| [private-dial](private-dial) | Make an HTTP request through a private byte stream. |
| [fastapi-tunnel](fastapi-tunnel) | Publish a FastAPI app through the direct ASGI helper. |
| [flask-tunnel](flask-tunnel) | Publish a Flask app through the direct WSGI helper. |
| [django-tunnel](django-tunnel) | Publish a Django app through the direct WSGI helper. |
| [forward-local-port](forward-local-port) | Publish an existing local TCP service through managed forwarding. |
| [aiohttp-local-forwarding](aiohttp-local-forwarding) | Publish an aiohttp app through managed local forwarding. |
| [webhook-receiver](webhook-receiver) | Verify webhook deliveries inside a FastAPI route. |
| [flask-webhook-receiver](flask-webhook-receiver) | Verify webhook deliveries inside a Flask route. |
| [django-webhook-receiver](django-webhook-receiver) | Verify webhook deliveries inside a Django view. |

See [HTTP applications](../docs/tunnels/000-http-applications.md) for the
server lifecycle and forwarding choices, and [private and TCP services](../docs/tunnels/001-private-and-tcp.md)
for a complete owner and caller setup. Each example explains its response and
how to stop it.
