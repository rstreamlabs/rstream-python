from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from socket import socket as Socket
from typing import cast

import pytest

from rstream.errors import RstreamRuntimeError
from rstream.stream import RstreamStream, pipe_stream_to_local


@pytest.mark.asyncio
async def test_rstream_stream_reads_and_writes_bytes() -> None:
    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            assert await reader.readexactly(4) == b"ping"
            writer.write(b"pong")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        host, port = _server_address(server)
        reader, writer = await asyncio.open_connection(host, port)
        async with RstreamStream(reader, writer) as stream:
            stream.write(b"ping")
            await stream.drain()
            assert await stream.readexactly(4) == b"pong"
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_pipe_stream_to_local_relays_bidirectional_bytes() -> None:
    echo_server = await asyncio.start_server(_echo_uppercase, "127.0.0.1", 0)
    stream_server, accepted = await _accept_one_stream()
    pipe_task: asyncio.Task[None] | None = None
    try:
        echo_host, echo_port = _server_address(echo_server)
        stream_host, stream_port = _server_address(stream_server)
        peer_reader, peer_writer = await asyncio.open_connection(
            stream_host,
            stream_port,
        )
        stream = await accepted()
        pipe_task = asyncio.create_task(
            pipe_stream_to_local(stream, echo_host, echo_port)
        )

        peer_writer.write(b"ping")
        await peer_writer.drain()

        assert await peer_reader.readexactly(4) == b"PING"

        peer_writer.close()
        await peer_writer.wait_closed()
        await asyncio.wait_for(pipe_task, timeout=5)
    finally:
        if pipe_task is not None and not pipe_task.done():
            pipe_task.cancel()
        echo_server.close()
        stream_server.close()
        await echo_server.wait_closed()
        await stream_server.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("host", "port"),
    [
        ("", 8000),
        ("127.0.0.1", 0),
        ("127.0.0.1", 65_536),
    ],
)
async def test_pipe_stream_to_local_rejects_invalid_endpoint(
    host: str,
    port: int,
) -> None:
    stream = cast(RstreamStream, object())

    with pytest.raises(RstreamRuntimeError) as exc:
        await pipe_stream_to_local(stream, host, port)

    assert exc.value.code == "ERR_RSTREAM_INVALID_LOCAL_ENDPOINT"


async def _echo_uppercase(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    try:
        while chunk := await reader.read(64 * 1024):
            writer.write(chunk.upper())
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def _accept_one_stream() -> tuple[
    asyncio.AbstractServer,
    Callable[[], Awaitable[RstreamStream]],
]:
    queue: asyncio.Queue[RstreamStream] = asyncio.Queue()

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        await queue.put(RstreamStream(reader, writer))

    server = await asyncio.start_server(handle, "127.0.0.1", 0)

    async def accepted() -> RstreamStream:
        return await queue.get()

    return server, accepted


def _server_address(server: asyncio.AbstractServer) -> tuple[str, int]:
    sockets_object = getattr(server, "sockets", None)
    assert sockets_object is not None
    sockets = cast(list[Socket], sockets_object)
    host, port = sockets[0].getsockname()[:2]
    return str(host), int(port)
