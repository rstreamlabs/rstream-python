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
| `created_at` | `str | None` | Event creation timestamp, when available. |
| `user_id` | `str | None` | User associated with the event, when available. |
| `workspace_id` | `str | None` | Workspace associated with the event, when available. |
| `project_id` | `str | None` | Project associated with the event, when available. |
| `cluster_id` | `str | None` | Cluster associated with the event, when available. |
| `object` | `Mapping[str, object]` | Event-specific resource snapshot. |
| `raw` | `Mapping[str, object]` | Complete decoded payload. |

The launch catalog contains `client.created`, `client.deleted`,
`tunnel.created`, and `tunnel.deleted`.

## Framework examples

The raw request body must be verified exactly as received. The repository
includes runnable receivers for the common cases:

| Framework | Example |
| --- | --- |
| FastAPI | [examples/webhook-receiver](../examples/webhook-receiver) |
| Flask | [examples/flask-webhook-receiver](../examples/flask-webhook-receiver) |
| Django | [examples/django-webhook-receiver](../examples/django-webhook-receiver) |
