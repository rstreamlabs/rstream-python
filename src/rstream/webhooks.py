"""Webhook signing and verification helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from rstream.errors import RuntimeError

WEBHOOK_SIGNATURE_HEADER = "rstream-signature"
WEBHOOK_EVENT_ID_HEADER = "rstream-event-id"
WEBHOOK_EVENT_TYPE_HEADER = "rstream-event-type"
WEBHOOK_ID_HEADER = "rstream-webhook-id"
WEBHOOK_DELIVERY_ID_HEADER = "rstream-delivery-id"
WEBHOOK_DELIVERABLE_EVENT_TYPES = (
    "client.created",
    "client.deleted",
    "tunnel.created",
    "tunnel.deleted",
)
JSONMapping = Mapping[str, object]


@dataclass(frozen=True)
class WebhookEvent:
    """Parsed webhook event."""

    id: str
    type: str
    created_at: str | None = None
    user_id: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None
    cluster_id: str | None = None
    object: JSONMapping = field(default_factory=dict)
    raw: JSONMapping = field(default_factory=dict)


def generate_signing_secret() -> str:
    encoded = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    return f"whsec_{encoded.rstrip('=')}"


def sign_payload(
    payload: bytes | str,
    secret: str,
    timestamp: int | None = None,
) -> str:
    _assert_secret(secret)
    timestamp_seconds = int(time.time()) if timestamp is None else timestamp
    if timestamp_seconds < 0:
        raise RuntimeError(
            "Invalid webhook signature timestamp.",
            code="ERR_RSTREAM_WEBHOOK_SIGNATURE",
        )
    raw_payload = _payload_bytes(payload)
    signed = f"{timestamp_seconds}.".encode() + raw_payload
    signature = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp_seconds},v1={signature}"


def build_headers(
    payload: bytes | str,
    event: WebhookEvent,
    secret: str,
    *,
    webhook_id: str,
    delivery_id: str,
    timestamp: int | None = None,
) -> Mapping[str, str]:
    return {
        WEBHOOK_SIGNATURE_HEADER: sign_payload(payload, secret, timestamp),
        WEBHOOK_EVENT_ID_HEADER: _required(event.id, "Webhook event id"),
        WEBHOOK_EVENT_TYPE_HEADER: _required(event.type, "Webhook event type"),
        WEBHOOK_ID_HEADER: _required(webhook_id, "Webhook id"),
        WEBHOOK_DELIVERY_ID_HEADER: _required(delivery_id, "Webhook delivery id"),
    }


def verify_event(
    payload: bytes | str,
    signature_header: str | Sequence[str],
    secret: str,
    *,
    tolerance: int = 300,
    received_at: int | None = None,
) -> WebhookEvent:
    _assert_secret(secret)
    if tolerance < 0:
        raise RuntimeError(
            "Invalid signature tolerance.",
            code="ERR_RSTREAM_WEBHOOK_SIGNATURE",
        )
    header = (
        signature_header[0]
        if isinstance(signature_header, Sequence)
        and not isinstance(signature_header, str)
        else signature_header
    )
    if not isinstance(header, str) or not header:
        raise RuntimeError(
            "No signature header.",
            code="ERR_RSTREAM_WEBHOOK_SIGNATURE",
        )
    timestamp, signatures = _parse_signature_header(header)
    now = int(time.time()) if received_at is None else received_at
    if abs(now - timestamp) > tolerance:
        raise RuntimeError(
            "Webhook signature timestamp outside tolerance.",
            code="ERR_RSTREAM_WEBHOOK_SIGNATURE",
        )
    raw_payload = _payload_bytes(payload)
    signed = f"{timestamp}.".encode() + raw_payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).digest()
    if not any(_signature_matches(signature, expected) for signature in signatures):
        raise RuntimeError(
            "Signature verification failed.",
            code="ERR_RSTREAM_WEBHOOK_SIGNATURE",
        )
    try:
        parsed = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Failed to parse webhook payload.",
            code="ERR_RSTREAM_WEBHOOK_PAYLOAD",
        ) from error
    return _event_from_json(parsed)


class Webhooks:
    """Object-oriented wrapper mirroring the JavaScript SDK helper."""

    def generate_signing_secret(self) -> str:
        return generate_signing_secret()

    def sign(
        self,
        payload: bytes | str,
        secret: str,
        timestamp: int | None = None,
    ) -> str:
        return sign_payload(payload, secret, timestamp)

    def event(
        self,
        payload: bytes | str,
        signature_header: str | Sequence[str],
        secret: str,
        *,
        tolerance: int = 300,
        received_at: int | None = None,
    ) -> WebhookEvent:
        return verify_event(
            payload,
            signature_header,
            secret,
            tolerance=tolerance,
            received_at=received_at,
        )


def _parse_signature_header(header: str) -> tuple[int, tuple[str, ...]]:
    timestamp: int | None = None
    signatures: list[str] = []
    for part in (item.strip() for item in header.split(",")):
        if part.startswith("t="):
            value = part[2:]
            if not value.isdigit():
                raise RuntimeError(
                    "Invalid signature timestamp.",
                    code="ERR_RSTREAM_WEBHOOK_SIGNATURE",
                )
            timestamp = int(value)
        elif part.startswith("v1="):
            signatures.append(part[3:])
    if timestamp is None or not signatures:
        raise RuntimeError(
            "Invalid signature header format.",
            code="ERR_RSTREAM_WEBHOOK_SIGNATURE",
        )
    return timestamp, tuple(signatures)


def _signature_matches(signature: str, expected: bytes) -> bool:
    if len(signature) != 64:
        return False
    try:
        parsed = bytes.fromhex(signature)
    except ValueError:
        return False
    return hmac.compare_digest(parsed, expected)


def _event_from_json(value: object) -> WebhookEvent:
    if not isinstance(value, Mapping):
        raise RuntimeError(
            "Webhook payload must be a JSON object.",
            code="ERR_RSTREAM_WEBHOOK_PAYLOAD",
        )
    event_id = value.get("id")
    event_type = value.get("type")
    created_at = value.get("created_at")
    event_object = value.get("object")
    if not isinstance(event_id, str) or not event_id.strip():
        raise RuntimeError(
            "Webhook event id is required.",
            code="ERR_RSTREAM_WEBHOOK_PAYLOAD",
        )
    if not isinstance(event_type, str) or not event_type.strip():
        raise RuntimeError(
            "Webhook event type is required.",
            code="ERR_RSTREAM_WEBHOOK_PAYLOAD",
        )
    if event_type not in WEBHOOK_DELIVERABLE_EVENT_TYPES:
        raise RuntimeError(
            "Webhook event type is not deliverable.",
            code="ERR_RSTREAM_WEBHOOK_PAYLOAD",
        )
    if created_at is not None and not isinstance(created_at, str):
        raise RuntimeError(
            "Webhook event created_at is invalid.",
            code="ERR_RSTREAM_WEBHOOK_PAYLOAD",
        )
    if not isinstance(event_object, Mapping):
        raise RuntimeError(
            "Webhook event object is required.",
            code="ERR_RSTREAM_WEBHOOK_PAYLOAD",
        )
    return WebhookEvent(
        id=event_id.strip(),
        type=event_type,
        created_at=created_at,
        user_id=_optional_string(value.get("user_id"), "user_id"),
        workspace_id=_optional_string(value.get("workspace_id"), "workspace_id"),
        project_id=_optional_string(value.get("project_id"), "project_id"),
        cluster_id=_optional_string(value.get("cluster_id"), "cluster_id"),
        object=_freeze_json_mapping(event_object),
        raw=_freeze_json_mapping(value),
    )


def _freeze_json_mapping(value: Mapping[object, object]) -> JSONMapping:
    return MappingProxyType(
        {str(key): _freeze_json_value(item) for key, item in value.items()}
    )


def _freeze_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_json_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_json_value(item) for item in value)
    return value


def _payload_bytes(payload: bytes | str) -> bytes:
    return payload if isinstance(payload, bytes) else payload.encode()


def _assert_secret(secret: str) -> None:
    if not secret.strip():
        raise RuntimeError(
            "Webhook signing secret is required.",
            code="ERR_RSTREAM_WEBHOOK_SECRET_REQUIRED",
        )


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise RuntimeError(
        f"Webhook event {field} is invalid.",
        code="ERR_RSTREAM_WEBHOOK_PAYLOAD",
    )


def _required(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise RuntimeError(f"{label} is required.", code="ERR_RSTREAM_WEBHOOK_PAYLOAD")
    return normalized
