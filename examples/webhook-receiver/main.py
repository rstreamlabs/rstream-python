from __future__ import annotations

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
        # Verify the unchanged raw body before running application logic.
        event = rstream.verify_event(payload, rstream_signature, secret)
    except rstream.RstreamError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    print("Received rstream event:", event.type, event.id)
    return {"received": True}
