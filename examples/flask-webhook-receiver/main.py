from __future__ import annotations

import os

from flask import Flask, jsonify, request

import rstream

app = Flask(__name__)


@app.post("/webhooks/rstream")
def rstream_webhook() -> tuple[object, int] | object:
    secret = os.environ.get("RSTREAM_WEBHOOK_SECRET")
    if secret is None:
        return jsonify(error="Webhook secret missing."), 500
    payload = request.get_data(cache=False)
    signature = request.headers.get("rstream-signature", "")
    try:
        # Verify the unchanged raw body before running application logic.
        event = rstream.verify_event(payload, signature, secret)
    except rstream.RstreamError as error:
        return jsonify(error=str(error)), 400
    return jsonify(
        event_id=event.id,
        event_type=event.type,
        received=True,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
