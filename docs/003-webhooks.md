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

Choose a receiver from the table above and start it on loopback port 8000
with `RSTREAM_WEBHOOK_SECRET` set to `whsec_local_example`. Use that value
only for this exercise. Save the following as `send_webhook.py` in another
terminal with the SDK installed and run `python send_webhook.py`.

```python
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import rstream

body = b'{"id":"evt_local","type":"tunnel.created","object":{"id":"tun_local"}}'
signature = rstream.sign_payload(body, "whsec_local_example")


def send(payload: bytes) -> int:
    request = Request(
        "http://127.0.0.1:8000/webhooks/rstream",
        data=payload,
        headers={
            "content-type": "application/json",
            "rstream-signature": signature,
        },
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status
    except HTTPError as error:
        return error.code


print("Signed bytes:", send(body))
print("Changed bytes:", send(body + b" "))
```

Expect `Signed bytes: 200` and `Changed bytes: 400`. The second request is
still JSON, but its bytes differ from those that were signed. A framework
may reject a missing header before calling the SDK verifier.

## Receive live events locally

Set the same test signing secret in the receiver and an authenticated CLI
session. Run the CLI forwarder against the receiver:

```sh
rstream events --webhook --webhook-secret "$RSTREAM_WEBHOOK_SECRET" \
  --events tunnel.created,tunnel.deleted \
  --forward-to http://127.0.0.1:8000/webhooks/rstream
```

In PowerShell, run the command on one line.

```powershell
rstream events --webhook --webhook-secret "$env:RSTREAM_WEBHOOK_SECRET" --events tunnel.created,tunnel.deleted --forward-to http://127.0.0.1:8000/webhooks/rstream
```

Create or close a tunnel in the selected project to send a signed request.
A hosted destination needs a reachable HTTPS receiver. Configure it
separately through the [product webhook guide](https://rstream.io/docs/integrations/webhooks).
Return 2xx after processing or durable storage, and use the signed event
ID for idempotency.
