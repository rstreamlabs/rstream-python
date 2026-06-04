from __future__ import annotations

import json
from collections.abc import MutableMapping
from typing import cast

import pytest

from rstream.webhooks import WebhookEvent, build_headers, sign_payload, verify_event


def test_webhook_signature_round_trip() -> None:
    payload = json.dumps(
        {
            "id": "evt_123",
            "type": "tunnel.created",
            "created_at": "2026-06-01T12:00:00Z",
            "project_id": "proj_123",
            "object": {"id": "tun_123", "labels": {"device": "camera-1"}},
        },
        separators=(",", ":"),
    )
    secret = "whsec_test"

    signature = sign_payload(payload, secret, timestamp=1_780_000_000)
    event = verify_event(
        payload,
        signature,
        secret,
        received_at=1_780_000_010,
    )

    assert event.id == "evt_123"
    assert event.type == "tunnel.created"
    assert event.created_at == "2026-06-01T12:00:00Z"
    assert event.project_id == "proj_123"
    assert event.object["id"] == "tun_123"
    assert event.raw["object"] == event.object

    with pytest.raises(TypeError):
        cast(MutableMapping[str, object], event.object)["id"] = "changed"

    labels = cast(MutableMapping[str, object], event.object["labels"])
    with pytest.raises(TypeError):
        labels["device"] = "changed"


def test_webhook_signature_rejects_invalid_secret() -> None:
    payload = '{"id":"evt_123","type":"client.created","object":{"id":"cli_123"}}'
    signature = sign_payload(payload, "whsec_valid", timestamp=10)

    with pytest.raises(Exception, match="Signature verification failed"):
        verify_event(payload, signature, "whsec_other", received_at=10)


def test_build_headers_includes_delivery_metadata() -> None:
    payload = '{"id":"evt_123","type":"client.created","object":{"id":"cli_123"}}'
    event = WebhookEvent(
        id="evt_123",
        type="client.created",
        object={"id": "cli_123"},
    )

    headers = build_headers(
        payload,
        event,
        "whsec_test",
        webhook_id="wh_123",
        delivery_id="del_123",
        timestamp=1,
    )

    assert headers["rstream-event-id"] == "evt_123"
    assert headers["rstream-event-type"] == "client.created"
    assert headers["rstream-webhook-id"] == "wh_123"
    assert headers["rstream-delivery-id"] == "del_123"
