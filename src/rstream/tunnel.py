"""Tunnel objects returned by the control channel."""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import suppress
from typing import Protocol

from rstream.errors import ProtocolError, RuntimeError
from rstream.stream import RstreamStream, pipe_stream_to_local
from rstream.types import TunnelProperties

DEFAULT_PUBLISHED_PORT = 443


class _StreamQueue:
    def __init__(self) -> None:
        self._streams: deque[RstreamStream] = deque()
        self._waiters: deque[asyncio.Future[RstreamStream]] = deque()
        self._close_error: BaseException | None = None

    async def get(self) -> RstreamStream:
        if self._streams:
            return self._streams.popleft()
        if self._close_error is not None:
            raise self._close_error
        future: asyncio.Future[RstreamStream] = (
            asyncio.get_running_loop().create_future()
        )
        self._waiters.append(future)
        try:
            return await future
        finally:
            with suppress(ValueError):
                self._waiters.remove(future)

    def put(self, stream: RstreamStream) -> bool:
        if self._close_error is not None:
            stream.close()
            return False
        while self._waiters:
            waiter = self._waiters.popleft()
            if waiter.done():
                continue
            waiter.set_result(stream)
            return True
        self._streams.append(stream)
        return True

    def close(self, error: BaseException) -> None:
        if self._close_error is not None:
            return
        self._close_error = error
        while self._streams:
            self._streams.popleft().close()
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.done():
                waiter.set_exception(error)


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
        self._queue = _StreamQueue()
        self._closed = False
        self._hard_closed = False
        self._forward_tasks: dict[asyncio.Task[None], RstreamStream] = {}

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
        stream = await self._queue.get()
        if self._hard_closed:
            stream.close()
            raise RuntimeError(
                "Tunnel closed.",
                code="ERR_RSTREAM_TUNNEL_CLOSED",
            )
        return stream

    async def close(self) -> None:
        if self._closed:
            self.on_close()
            await self.wait_forwarders_closed()
            return
        await self._control.close_tunnel(self.id)
        await self.wait_forwarders_closed()

    async def forward_to(self, host: str, port: int) -> None:
        _validate_local_endpoint(host, port)
        async for stream in self:
            task = asyncio.create_task(pipe_stream_to_local(stream, host, port))
            self._forward_tasks[task] = stream
            task.add_done_callback(self._forward_task_done)

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
        return self._queue.put(stream)

    def on_close(
        self,
        error: BaseException | None = None,
        *,
        preserve_forwarders: bool = False,
    ) -> None:
        if not preserve_forwarders:
            self._hard_closed = True
        if not self._closed:
            self._closed = True
            self._queue.close(
                error
                or RuntimeError(
                    "Tunnel closed.",
                    code="ERR_RSTREAM_TUNNEL_CLOSED",
                )
            )
        if not preserve_forwarders:
            for task, stream in tuple(self._forward_tasks.items()):
                stream.close()
                task.cancel()

    async def wait_forwarders_closed(self) -> None:
        if not self._forward_tasks:
            return
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*self._forward_tasks, return_exceptions=True)

    def _forward_task_done(self, task: asyncio.Task[None]) -> None:
        self._forward_tasks.pop(task, None)
        if not task.cancelled():
            task.exception()


def format_forwarding_address(properties: TunnelProperties) -> str:
    published = _published_host(properties)
    if published is not None:
        if properties.protocol == "http":
            return f"https://{published}"
        if properties.protocol == "tls":
            return f"{published} (tls)"
        if properties.protocol == "tcp":
            return f"{published} (tcp)"
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
        if properties.protocol in {"tls", "tcp"} or port != DEFAULT_PUBLISHED_PORT:
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
