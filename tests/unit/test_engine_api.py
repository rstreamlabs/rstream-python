from __future__ import annotations

import json

import httpx
import pytest

from rstream.engine_api import (
    ClientFilters,
    TunnelFilters,
    _decode_event,
    event_from_json,
    list_inventory,
    tunnel_inventory_from_json,
    watch_params_json,
)
from rstream.errors import RstreamRuntimeError


def test_tunnel_filters_to_json_includes_set_fields_and_labels() -> None:
    filters = TunnelFilters(
        type="bytestream",
        status="active",
        publish=False,
        labels={"role": "inference", "model": None},
    )

    assert filters.to_json() == {
        "type": "bytestream",
        "status": "active",
        "publish": False,
        "labels": {"role": "inference", "model": None},
    }


def test_client_filters_to_json_skips_unset_fields() -> None:
    assert ClientFilters().to_json() == {}
    assert ClientFilters(status="connected").to_json() == {"status": "connected"}


def test_watch_params_json_combines_filter_groups() -> None:
    assert watch_params_json(None, None) is None
    params = watch_params_json(TunnelFilters(type="bytestream"), ClientFilters())
    assert params == {"tunnels": {"type": "bytestream"}, "clients": {}}


def test_tunnel_inventory_from_json_parses_properties_and_status() -> None:
    inventory = tunnel_inventory_from_json(
        {
            "id": "tun_1",
            "name": "worker-a",
            "type": "bytestream",
            "publish": False,
            "labels": {"role": "inference"},
            "status": "active",
            "client_id": "cli_9",
            "port": 443,
        }
    )

    assert inventory.properties.id == "tun_1"
    assert inventory.properties.name == "worker-a"
    assert inventory.properties.labels == {"role": "inference"}
    assert inventory.properties.port == 443
    assert inventory.status == "active"
    assert inventory.client_id == "cli_9"
    assert inventory.raw["id"] == "tun_1"


def test_event_from_json_extracts_envelope_and_object() -> None:
    event = event_from_json(
        {
            "id": "evt_1",
            "type": "tunnel.created",
            "created_at": "2026-06-10T12:00:00Z",
            "project_id": "prj_1",
            "object": {"id": "tun_1", "status": "active"},
        }
    )

    assert event.type == "tunnel.created"
    assert event.id == "evt_1"
    assert event.project_id == "prj_1"
    assert event.object is not None
    assert event.object["id"] == "tun_1"


def test_decode_event_skips_blank_and_rejects_invalid_json() -> None:
    assert _decode_event("") is None
    assert _decode_event("   ") is None
    with pytest.raises(RstreamRuntimeError, match="Invalid event JSON"):
        _decode_event("{not-json")


async def test_list_inventory_sends_params_and_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url).split("?")[0]
        seen["params"] = json.loads(request.url.params["params"])
        seen["authorization"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json=[{"id": "tun_1", "status": "active"}],
        )

    _install_mock_transport(monkeypatch, handler)
    items = await list_inventory(
        engine="engine.example.test:443",
        token="secret",
        path="/tunnels",
        params_json={"filters": {"type": "bytestream"}},
        tls=None,
    )

    assert seen["url"] == "https://engine.example.test/api/tunnels"
    assert seen["params"] == {"filters": {"type": "bytestream"}}
    assert seen["authorization"] == "Bearer secret"
    assert len(items) == 1
    assert items[0]["id"] == "tun_1"


async def test_list_inventory_raises_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    _install_mock_transport(monkeypatch, handler)
    with pytest.raises(RstreamRuntimeError, match="403"):
        await list_inventory(
            engine="engine.example.test:443",
            token=None,
            path="/tunnels",
            params_json=None,
            tls=None,
        )


def _install_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: object,
) -> None:
    real_async_client = httpx.AsyncClient

    def patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        kwargs["transport"] = httpx.MockTransport(handler)  # type: ignore[arg-type]
        return real_async_client(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", patched)


async def test_event_stream_iterates_and_closes_source() -> None:
    from collections.abc import AsyncIterator

    from rstream.engine_api import Event, EventStream

    closed = False

    async def generate() -> AsyncIterator[Event]:
        nonlocal closed
        try:
            yield event_from_json({"type": "tunnel.created"})
            yield event_from_json({"type": "tunnel.deleted"})
        finally:
            closed = True

    async with EventStream(generate()) as events:
        first = await events.__anext__()
        assert isinstance(first, Event)
        assert first.type == "tunnel.created"
    assert closed
