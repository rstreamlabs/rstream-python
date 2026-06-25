"""Engine API access: live inventory listing and real-time event watch.

These helpers call the engine HTTP API at ``https://<engine>/api`` with the
runtime token, and stream real-time events from ``/api/sse`` or
``/api/websocket``.
"""

from __future__ import annotations

import json
import ssl
from collections.abc import AsyncGenerator, AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from rstream.config import TLSOptions
from rstream.errors import RuntimeError
from rstream.types import TunnelProperties

WatchTransport = Literal["sse", "websocket"]


@dataclass(frozen=True)
class TunnelFilters:
    """Filters accepted by :meth:`rstream.Client.list_tunnels` and tunnel watches.

    A label mapped to ``None`` matches any value for that key.
    """

    id: str | None = None
    name: str | None = None
    type: str | None = None
    status: str | None = None
    client_id: str | None = None
    user_id: str | None = None
    protocol: str | None = None
    hostname: str | None = None
    publish: bool | None = None
    http_version: str | None = None
    labels: Mapping[str, str | None] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        out: dict[str, object] = {}
        for key in (
            "id",
            "name",
            "type",
            "status",
            "client_id",
            "user_id",
            "protocol",
            "hostname",
            "publish",
            "http_version",
        ):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.labels:
            out["labels"] = dict(self.labels)
        return out


@dataclass(frozen=True)
class ClientFilters:
    """Filters accepted by :meth:`rstream.Client.list_clients` and client watches."""

    id: str | None = None
    status: str | None = None
    user_id: str | None = None
    agent: str | None = None
    channel: str | None = None
    version: str | None = None
    os: str | None = None
    arch: str | None = None
    protocol_version: str | None = None
    labels: Mapping[str, str | None] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        out: dict[str, object] = {}
        for key in (
            "id",
            "status",
            "user_id",
            "agent",
            "channel",
            "version",
            "os",
            "arch",
            "protocol_version",
        ):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.labels:
            out["labels"] = dict(self.labels)
        return out


@dataclass(frozen=True)
class TunnelInventory:
    """One live tunnel as reported by the engine inventory."""

    properties: TunnelProperties
    status: str | None
    client_id: str | None
    raw: Mapping[str, object]


@dataclass(frozen=True)
class Event:
    """One real-time event delivered by the engine watch endpoints."""

    type: str
    id: str | None
    created_at: str | None
    user_id: str | None
    workspace_id: str | None
    project_id: str | None
    cluster_id: str | None
    raw: Mapping[str, object]
    object: Mapping[str, object] | None


def event_from_json(data: Mapping[str, object]) -> Event:
    obj = data.get("object")
    return Event(
        type=str(data.get("type", "")),
        id=_optional_str(data, "id"),
        created_at=_optional_str(data, "created_at"),
        user_id=_optional_str(data, "user_id"),
        workspace_id=_optional_str(data, "workspace_id"),
        project_id=_optional_str(data, "project_id"),
        cluster_id=_optional_str(data, "cluster_id"),
        object=obj if isinstance(obj, Mapping) else None,
        raw=data,
    )


def tunnel_inventory_from_json(data: Mapping[str, object]) -> TunnelInventory:
    return TunnelInventory(
        properties=tunnel_properties_from_json(data),
        status=_optional_str(data, "status"),
        client_id=_optional_str(data, "client_id"),
        raw=data,
    )


def tunnel_properties_from_json(data: Mapping[str, object]) -> TunnelProperties:
    labels = data.get("labels")
    return TunnelProperties(
        id=_optional_str(data, "id"),
        creation_date=_optional_datetime(data, "creation_date"),
        name=_optional_str(data, "name"),
        type=_optional_str(data, "type"),  # type: ignore[arg-type]
        publish=_optional_bool(data, "publish"),
        protocol=_optional_str(data, "protocol"),  # type: ignore[arg-type]
        labels=dict(labels) if isinstance(labels, Mapping) else {},
        geo_ip=_string_tuple(data, "geo_ip"),
        trusted_ips=_string_tuple(data, "trusted_ips"),
        host=_optional_str(data, "host"),
        tls_mode=_optional_str(data, "tls_mode"),  # type: ignore[arg-type]
        tls_alpns=_string_tuple(data, "tls_alpns"),
        tls_min_version=_optional_str(data, "tls_min_version"),
        tls_ciphers=_string_tuple(data, "tls_ciphers"),
        mtls_auth=_optional_bool(data, "mtls_auth"),
        http_version=_optional_str(data, "http_version"),  # type: ignore[arg-type]
        http_use_tls=_optional_bool(data, "http_use_tls"),
        token_auth=_optional_bool(data, "token_auth"),
        rstream_auth=_optional_bool(data, "rstream_auth"),
        hostname=_optional_str(data, "hostname"),
        port=_optional_int(data, "port"),
        upstream_tls=_optional_bool(data, "upstream_tls"),
    )


class EventStream:
    """Async iterator over engine events, also usable as an async context manager.

    Iterating with ``async for`` works directly. Wrapping the stream in
    ``async with`` guarantees the underlying connection is closed when the
    block exits, including on cancellation.
    """

    def __init__(self, source: AsyncIterator[Event]) -> None:
        self._source = source

    def __aiter__(self) -> EventStream:
        return self

    async def __anext__(self) -> Event:
        return await self._source.__anext__()

    async def aclose(self) -> None:
        aclose = getattr(self._source, "aclose", None)
        if aclose is not None:
            await aclose()

    async def __aenter__(self) -> EventStream:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        await self.aclose()


def watch_params_json(
    tunnels: TunnelFilters | None,
    clients: ClientFilters | None,
) -> dict[str, object] | None:
    params: dict[str, object] = {}
    if tunnels is not None:
        params["tunnels"] = tunnels.to_json()
    if clients is not None:
        params["clients"] = clients.to_json()
    return params or None


def _require_httpx() -> Any:
    try:
        import httpx
    except ImportError as error:
        raise RuntimeError(
            "Install rstream[api] to call the engine API.",
            code="ERR_RSTREAM_API_EXTRA_REQUIRED",
        ) from error
    return httpx


def _httpx_verify(tls: TLSOptions | None) -> object:
    if tls is None:
        return True
    if tls.insecure_skip_verify:
        return False
    if tls.ca_file is not None:
        context = ssl.create_default_context(cafile=tls.ca_file)
        return context
    return True


async def list_inventory(
    *,
    engine: str,
    token: str | None,
    path: str,
    params_json: Mapping[str, object] | None,
    tls: TLSOptions | None,
) -> list[Mapping[str, object]]:
    httpx = _require_httpx()
    url = f"https://{engine}/api{path}"
    query: dict[str, str] = {}
    if params_json:
        query["params"] = json.dumps(params_json)
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(verify=_httpx_verify(tls), timeout=15) as client:
        response = await client.get(url, params=query, headers=headers)
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(
            f"Engine API error {response.status_code}: {response.text}",
            code="ERR_RSTREAM_ENGINE_API_HTTP",
        )
    value = response.json()
    if not isinstance(value, list):
        raise RuntimeError(
            "Engine API returned an unexpected payload.",
            code="ERR_RSTREAM_ENGINE_API_PAYLOAD",
        )
    return [item for item in value if isinstance(item, Mapping)]


async def watch_events(
    *,
    engine: str,
    token: str | None,
    params_json: Mapping[str, object] | None,
    tls: TLSOptions | None,
    transport: WatchTransport,
) -> AsyncGenerator[Event, None]:
    if transport == "websocket":
        async for event in _watch_websocket(
            engine=engine, token=token, params_json=params_json, tls=tls
        ):
            yield event
        return
    if transport != "sse":
        raise RuntimeError(
            f"Unsupported watch transport {transport!r}.",
            code="ERR_RSTREAM_WATCH_TRANSPORT",
        )
    async for event in _watch_sse(
        engine=engine, token=token, params_json=params_json, tls=tls
    ):
        yield event


async def _watch_sse(
    *,
    engine: str,
    token: str | None,
    params_json: Mapping[str, object] | None,
    tls: TLSOptions | None,
) -> AsyncIterator[Event]:
    httpx = _require_httpx()
    url = f"https://{engine}/api/sse"
    query: dict[str, str] = {}
    if params_json:
        query["params"] = json.dumps(params_json)
    headers = {"Accept": "text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with (
        httpx.AsyncClient(verify=_httpx_verify(tls), timeout=None) as client,
        client.stream("GET", url, params=query, headers=headers) as response,
    ):
        if response.status_code < 200 or response.status_code >= 300:
            body = (await response.aread()).decode(errors="replace")
            raise RuntimeError(
                f"Engine SSE error {response.status_code}: {body}",
                code="ERR_RSTREAM_ENGINE_API_HTTP",
            )
        data_lines: list[str] = []
        async for line in response.aiter_lines():
            if line == "":
                if data_lines:
                    payload = "\n".join(data_lines)
                    data_lines = []
                    event = _decode_event(payload)
                    if event is not None:
                        yield event
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())


async def _watch_websocket(
    *,
    engine: str,
    token: str | None,
    params_json: Mapping[str, object] | None,
    tls: TLSOptions | None,
) -> AsyncIterator[Event]:
    try:
        import websockets
    except ImportError as error:
        raise RuntimeError(
            "Install rstream[realtime] to watch events over WebSocket.",
            code="ERR_RSTREAM_REALTIME_EXTRA_REQUIRED",
        ) from error
    url = f"wss://{engine}/api/websocket"
    if params_json:
        from urllib.parse import quote

        url += f"?params={quote(json.dumps(params_json))}"
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    ssl_context: ssl.SSLContext | None = None
    verify = _httpx_verify(tls)
    if verify is False:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    elif isinstance(verify, ssl.SSLContext):
        ssl_context = verify
    if ssl_context is not None:
        connect = websockets.connect(url, additional_headers=headers, ssl=ssl_context)
    else:
        connect = websockets.connect(url, additional_headers=headers)
    async with connect as connection:
        async for message in connection:
            if isinstance(message, bytes):
                message = message.decode(errors="replace")
            event = _decode_event(message)
            if event is not None:
                yield event


def _decode_event(payload: str) -> Event | None:
    payload = payload.strip()
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Invalid event JSON: {error}",
            code="ERR_RSTREAM_EVENT_JSON",
        ) from error
    if not isinstance(data, Mapping):
        return None
    return event_from_json(data)


def _optional_str(data: Mapping[str, object], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) else None


def _optional_bool(data: Mapping[str, object], key: str) -> bool | None:
    value = data.get(key)
    return value if isinstance(value, bool) else None


def _optional_int(data: Mapping[str, object], key: str) -> int | None:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_datetime(data: Mapping[str, object], key: str) -> datetime | None:
    value = data.get(key)
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _string_tuple(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
