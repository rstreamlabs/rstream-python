# Webhooks

The SDK includes a small helper for webhook receivers. It verifies the raw
request body against the `rstream-signature` header and returns a parsed event.

## FastAPI receiver

```python
import os

from fastapi import FastAPI, Header, HTTPException, Request

import rstream

app = FastAPI()


@app.post("/webhooks/rstream")
async def rstream_webhook(
    request: Request,
    rstream_signature: str = Header(alias="rstream-signature"),
) -> dict[str, bool]:
    secret = os.environ.get("RSTREAM_WEBHOOK_SECRET")
    if secret is None:
        raise HTTPException(status_code=500, detail="Webhook secret missing.")

    payload = await request.body()
    try:
        event = rstream.verify_event(payload, rstream_signature, secret)
    except rstream.RstreamError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    resource_id = event.object.get("id")
    if event.type == "tunnel.created":
        print("Tunnel created:", resource_id)

    return {"received": True}
```

## Headers

| Header | Purpose |
| --- | --- |
| `rstream-signature` | HMAC signature for the raw body. |
| `rstream-event-id` | Event identifier. |
| `rstream-event-type` | Event type. |
| `rstream-webhook-id` | Webhook endpoint identifier. |
| `rstream-delivery-id` | Delivery identifier. |

The signature header uses `t=<timestamp>,v1=<hex hmac>`. During rotation, a
single request may contain more than one `v1` signature.

## Event payload

`verify_event` returns a `WebhookEvent` parsed from the signed JSON payload.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | `str` | Event identifier for idempotency. |
| `type` | `str` | Deliverable event type. |
| `created_at` | `str \| None` | Event creation timestamp, when available. |
| `user_id` | `str \| None` | User associated with the event, when available. |
| `workspace_id` | `str \| None` | Workspace associated with the event, when available. |
| `project_id` | `str \| None` | Project associated with the event, when available. |
| `cluster_id` | `str \| None` | Cluster associated with the event, when available. |
| `object` | `Mapping[str, object]` | Event-specific resource snapshot. |
| `raw` | `Mapping[str, object]` | Complete decoded payload. |

The Python parser accepts `client.created`, `client.deleted`, `tunnel.created`
and `tunnel.deleted`. Select those types in the webhook destination's event
filters. It rejects WebTTY events even when their signatures are valid; use a
receiver that supports the [service event catalog](https://rstream.io/docs/integrations/webhooks#receiver-compatibility)
when subscribing to those events.

## Framework examples

The raw request body must be verified exactly as received. The repository
includes runnable receivers for the common cases:

| Framework | Example |
| --- | --- |
| FastAPI | [examples/webhook-receiver](../examples/webhook-receiver) |
| Flask | [examples/flask-webhook-receiver](../examples/flask-webhook-receiver) |
| Django | [examples/django-webhook-receiver](../examples/django-webhook-receiver) |

## Try a local delivery

Start the FastAPI receiver from `examples/webhook-receiver` using its README.
In another terminal, use a configured CLI context and the same signing secret:

```sh
rstream events --webhook --webhook-secret "$RSTREAM_WEBHOOK_SECRET" \
  --events tunnel.created,tunnel.deleted \
  --forward-to http://127.0.0.1:8000/webhooks/rstream
```

Set `RSTREAM_WEBHOOK_SECRET` in both terminals before starting either process.
Creating or closing a disposable tunnel in that project produces a verified
request; the receiver prints its event ID and returns 200. A malformed signature
returns 400. The CLI forwards live events locally; it does not configure durable
Control plane destinations or retain retries after exit. A hosted destination
cannot reach a loopback URL directly: publish a receiver deliberately and use
its HTTPS address for that separate workflow.

Return 2xx after processing or durable storage, and use `event.id` for idempotency.

For a deterministic first check without a configured Engine, run the receiver with
`RSTREAM_WEBHOOK_SECRET=whsec_local_example`. From the same example directory in
another activated terminal, send one synthetic event:

```sh
RSTREAM_WEBHOOK_SECRET=whsec_local_example python - <<'PYTHON'
import os
from urllib.request import Request, urlopen
import rstream

body = b'{"id":"evt_local_example","type":"tunnel.created","object":{"id":"tun_local"}}'
request = Request("http://127.0.0.1:8000/webhooks/rstream", data=body, headers={
    "content-type": "application/json",
    "rstream-signature": rstream.sign_payload(body, os.environ["RSTREAM_WEBHOOK_SECRET"]),
})
with urlopen(request, timeout=5) as response:
    print(response.status, response.read().decode())
PYTHON
```

The expected result is `200 {"received":true}`. This fixture secret is deliberately
public and belongs only to the local example, never to a real webhook destination.
