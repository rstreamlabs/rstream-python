"""Tunnel objects returned by the control channel."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Protocol

from rstream.errors import ProtocolError, RuntimeError
from rstream.stream import RstreamStream, pipe_stream_to_local
from rstream.types import TunnelProperties

DEFAULT_PUBLISHED_PORT = 443


class _TunnelControl(Protocol):
    async def close_tunnel(self, tunnel_id: str) -> None: ...


class BytestreamTunnel:
    """A bytestream tunnel opened on the engine."""

    def __init__(
        self,
        control: _TunnelControl,
        properties: TunnelProperties,
    ) -> None:
        if properties.id is None:
            raise ProtocolError(
                "Engine did not return a tunnel ID.",
                code="ERR_RSTREAM_PROTOCOL",
            )
        self._control = control
        self._properties = properties
        self._queue: asyncio.Queue[RstreamStream | BaseException | None] = (
            asyncio.Queue()
        )
        self._closed = False
        self._forward_tasks: set[asyncio.Task[None]] = set()

    @property
    def id(self) -> str:
        return self._properties.id or ""

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def forwarding_address(self) -> str:
        return format_forwarding_address(self._properties)

    @property
    def properties(self) -> TunnelProperties:
        return self._properties

    async def accept(self) -> RstreamStream:
        item = await self._queue.get()
        if item is None:
            raise RuntimeError(
                "Tunnel closed.",
                code="ERR_RSTREAM_TUNNEL_CLOSED",
            )
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self) -> None:
        if self._closed:
            return
        await self._control.close_tunnel(self.id)

    async def forward_to(self, host: str, port: int) -> None:
        _validate_local_endpoint(host, port)
        async for stream in self:
            task = asyncio.create_task(pipe_stream_to_local(stream, host, port))
            self._forward_tasks.add(task)
            task.add_done_callback(self._forward_tasks.discard)

    def __aiter__(self) -> BytestreamTunnel:
        return self

    async def __anext__(self) -> RstreamStream:
        try:
            return await self.accept()
        except RuntimeError as error:
            if error.code == "ERR_RSTREAM_TUNNEL_CLOSED":
                raise StopAsyncIteration from error
            raise

    def deliver(self, stream: RstreamStream) -> bool:
        if self._closed:
            stream.close()
            return False
        self._queue.put_nowait(stream)
        return True

    def on_close(self, error: BaseException | None = None) -> None:
        if self._closed:
            return
        self._closed = True
        if error is not None:
            self._queue.put_nowait(error)
        self._queue.put_nowait(None)
        for task in self._forward_tasks:
            task.cancel()

    async def wait_forwarders_closed(self) -> None:
        if not self._forward_tasks:
            return
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*self._forward_tasks, return_exceptions=True)


def format_forwarding_address(properties: TunnelProperties) -> str:
    published = _published_host(properties)
    if published is not None:
        if properties.protocol == "http":
            return f"https://{published}"
        if properties.protocol == "tls":
            return f"{published} (tls)"
        if properties.protocol == "dtls":
            return f"{published} (dtls)"
        if properties.protocol == "quic":
            return f"{published} (quic)"
        return published
    if properties.name is not None:
        return f"rstrm://{properties.name} (unpublished)"
    if properties.id is not None:
        return f"rstrm://{properties.id} (unpublished)"
    raise RuntimeError(
        "Invalid tunnel properties: no host, name, or ID.",
        code="ERR_RSTREAM_INVALID_TUNNEL",
    )


def _published_host(properties: TunnelProperties) -> str | None:
    if properties.hostname and properties.hostname.strip():
        port = properties.port or DEFAULT_PUBLISHED_PORT
        if properties.protocol == "tls" or port != DEFAULT_PUBLISHED_PORT:
            return f"{properties.hostname}:{port}"
        return properties.hostname
    if properties.host and properties.host.strip():
        return properties.host
    return None


def _validate_local_endpoint(host: str, port: int) -> None:
    if not host.strip():
        raise RuntimeError(
            "Local forward host is required.",
            code="ERR_RSTREAM_INVALID_LOCAL_ENDPOINT",
        )
    if not 1 <= port <= 65_535:
        raise RuntimeError(
            "Local forward port must be between 1 and 65535.",
            code="ERR_RSTREAM_INVALID_LOCAL_ENDPOINT",
        )
