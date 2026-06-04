from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from socket import socket as Socket
from typing import cast

import pytest

import rstream
import rstream.asgi as rstream_asgi


@pytest.mark.asyncio
async def test_asgi_serve_dispatches_http_request_without_local_hop() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    async def app(
        scope: dict[str, object],
        receive: rstream_asgi.Receive,
        send: rstream_asgi.Send,
    ) -> None:
        message = await receive()
        assert scope["type"] == "http"
        assert scope["method"] == "POST"
        assert scope["path"] == "/devices"
        assert scope["query_string"] == b"online=true"
        assert message["body"] == b"device=cam-1"
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    task = asyncio.create_task(rstream_asgi.serve(app, tunnel))
    try:
        client_writer.write(
            b"POST /devices?online=true HTTP/1.1\r\n"
            b"Host: example.test\r\n"
            b"Content-Length: 12\r\n\r\n"
            b"device=cam-1"
        )
        await client_writer.drain()

        response = await _read_until(client_reader, b"ok")
        assert b"HTTP/1.1 200" in response
        assert b"ok" in response
    finally:
        task.cancel()
        client_writer.close()
        await asyncio.gather(task, return_exceptions=True)
        await client_writer.wait_closed()


@pytest.mark.asyncio
async def test_asgi_serve_streams_chunked_request_body() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()
    first_chunk_received = asyncio.Event()

    async def app(
        scope: rstream_asgi.ASGIScope,
        receive: rstream_asgi.Receive,
        send: rstream_asgi.Send,
    ) -> None:
        chunks: list[bytes] = []
        while True:
            message = await receive()
            assert message["type"] == "http.request"
            body = message.get("body", b"")
            assert isinstance(body, bytes)
            if body:
                chunks.append(body)
                first_chunk_received.set()
            if not bool(message.get("more_body", False)):
                break
        assert b"".join(chunks) == b"hello world"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"streamed"})

    task = asyncio.create_task(rstream_asgi.serve(app, tunnel))
    try:
        client_writer.write(
            b"POST /chunked HTTP/1.1\r\n"
            b"Host: example.test\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n"
            b"5\r\nhello\r\n"
        )
        await client_writer.drain()
        await asyncio.wait_for(first_chunk_received.wait(), timeout=1)
        client_writer.write(b"6\r\n world\r\n0\r\n\r\n")
        await client_writer.drain()

        response = await _read_until(client_reader, b"streamed")
        assert b"HTTP/1.1 200" in response
        assert b"streamed" in response
    finally:
        task.cancel()
        client_writer.close()
        await asyncio.gather(task, return_exceptions=True)
        await client_writer.wait_closed()


@pytest.mark.asyncio
async def test_asgi_serve_rejects_oversized_body() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    async def app(
        scope: rstream_asgi.ASGIScope,
        receive: rstream_asgi.Receive,
        send: rstream_asgi.Send,
    ) -> None:
        raise AssertionError("ASGI app should not receive oversized payloads")

    task = asyncio.create_task(rstream_asgi.serve(app, tunnel, max_body_size=4))
    try:
        client_writer.write(
            b"POST /devices HTTP/1.1\r\n"
            b"Host: example.test\r\n"
            b"Content-Length: 5\r\n\r\n"
            b"abcde"
        )
        await client_writer.drain()

        response = await _read_until(client_reader, b"Payload too large.")
        assert b"HTTP/1.1 413" in response
    finally:
        task.cancel()
        client_writer.close()
        await asyncio.gather(task, return_exceptions=True)
        await client_writer.wait_closed()


@pytest.mark.asyncio
async def test_asgi_serve_times_out_incomplete_request() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    async def app(
        scope: rstream_asgi.ASGIScope,
        receive: rstream_asgi.Receive,
        send: rstream_asgi.Send,
    ) -> None:
        raise AssertionError("ASGI app should not receive incomplete requests")

    task = asyncio.create_task(rstream_asgi.serve(app, tunnel, read_timeout=0.05))
    try:
        client_writer.write(b"GET /slow HTTP/1.1\r\n")
        await client_writer.drain()

        response = await _read_until(client_reader, b"Request timeout.")
        assert b"HTTP/1.1 408" in response
    finally:
        task.cancel()
        client_writer.close()
        await asyncio.gather(task, return_exceptions=True)
        await client_writer.wait_closed()


@pytest.mark.asyncio
async def test_asgi_serve_returns_500_before_response_start() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    async def app(
        scope: rstream_asgi.ASGIScope,
        receive: rstream_asgi.Receive,
        send: rstream_asgi.Send,
    ) -> None:
        raise RuntimeError("boom")

    task = asyncio.create_task(rstream_asgi.serve(app, tunnel))
    try:
        client_writer.write(b"GET /broken HTTP/1.1\r\nHost: example.test\r\n\r\n")
        await client_writer.drain()

        response = await _read_until(client_reader, b"Internal server error.")
        assert b"HTTP/1.1 500" in response
    finally:
        task.cancel()
        client_writer.close()
        await asyncio.gather(task, return_exceptions=True)
        await client_writer.wait_closed()


@pytest.mark.asyncio
async def test_asgi_serve_handles_concurrent_streams() -> None:
    tunnel, connect, server = await _queue_tunnel()
    task = asyncio.create_task(
        rstream_asgi.serve(
            _echo_asgi_app,
            tunnel,
        )
    )
    try:
        responses = await asyncio.gather(
            *(connect_and_get(connect, f"/request-{index}") for index in range(12))
        )
        assert responses == [f"request-{index}".encode() for index in range(12)]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_asgi_serve_rejects_invalid_limits() -> None:
    tunnel = cast(rstream.BytestreamTunnel, object())

    with pytest.raises(ValueError, match="max_header_size"):
        await rstream_asgi.serve(_echo_asgi_app, tunnel, max_header_size=0)

    with pytest.raises(ValueError, match="max_body_size"):
        await rstream_asgi.serve(_echo_asgi_app, tunnel, max_body_size=-1)

    with pytest.raises(ValueError, match="read_timeout"):
        await rstream_asgi.serve(_echo_asgi_app, tunnel, read_timeout=0)


@dataclass
class _OneStreamTunnel:
    stream: rstream.RstreamStream
    server: asyncio.AbstractServer
    delivered: bool = False

    def __aiter__(self) -> _OneStreamTunnel:
        return self

    async def __anext__(self) -> rstream.RstreamStream:
        if self.delivered:
            self.server.close()
            await self.server.wait_closed()
            await asyncio.Event().wait()
        self.delivered = True
        return self.stream


async def _one_stream_tunnel() -> tuple[
    rstream.BytestreamTunnel,
    asyncio.StreamReader,
    asyncio.StreamWriter,
]:
    queue: asyncio.Queue[rstream.RstreamStream] = asyncio.Queue()

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        await queue.put(rstream.RstreamStream(reader, writer))

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    host, port = _server_address(server)
    client_reader, client_writer = await asyncio.open_connection(host, port)
    stream = await queue.get()
    return (
        cast(rstream.BytestreamTunnel, _OneStreamTunnel(stream, server)),
        client_reader,
        client_writer,
    )


@dataclass
class _QueueTunnel:
    queue: asyncio.Queue[rstream.RstreamStream]
    server: asyncio.AbstractServer

    def __aiter__(self) -> _QueueTunnel:
        return self

    async def __anext__(self) -> rstream.RstreamStream:
        return await self.queue.get()


async def _queue_tunnel() -> tuple[
    rstream.BytestreamTunnel,
    Callable[[], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]],
    asyncio.AbstractServer,
]:
    queue: asyncio.Queue[rstream.RstreamStream] = asyncio.Queue()

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        await queue.put(rstream.RstreamStream(reader, writer))

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    host, port = _server_address(server)

    async def connect() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await asyncio.open_connection(host, port)

    return cast(rstream.BytestreamTunnel, _QueueTunnel(queue, server)), connect, server


async def _echo_asgi_app(
    scope: rstream_asgi.ASGIScope,
    receive: rstream_asgi.Receive,
    send: rstream_asgi.Send,
) -> None:
    await receive()
    path = cast(str, scope["path"]).strip("/").encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-length", str(len(path)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": path})


async def connect_and_get(
    connect: Callable[[], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]],
    path: str,
) -> bytes:
    reader, writer = await connect()
    try:
        writer.write(f"GET {path} HTTP/1.1\r\nHost: example.test\r\n\r\n".encode())
        await writer.drain()
        response = await _read_until(reader, path.strip("/").encode())
        return response.split(b"\r\n\r\n", 1)[1]
    finally:
        writer.close()
        await writer.wait_closed()


def _server_address(server: asyncio.AbstractServer) -> tuple[str, int]:
    sockets_object = getattr(server, "sockets", None)
    assert sockets_object is not None
    sockets = cast(list[Socket], sockets_object)
    host, port = sockets[0].getsockname()[:2]
    return str(host), int(port)


async def _read_until(reader: asyncio.StreamReader, needle: bytes) -> bytes:
    data = bytearray()
    while needle not in data:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=1)
        if chunk == b"":
            raise AssertionError(f"stream closed before {needle!r} was received")
        data.extend(chunk)
    return bytes(data)
