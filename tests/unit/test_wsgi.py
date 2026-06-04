from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from socket import socket as Socket
from typing import cast

import pytest

import rstream
import rstream.wsgi as rstream_wsgi


@pytest.mark.asyncio
async def test_wsgi_serve_dispatches_http_request_without_local_hop() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    def app(
        environ: dict[str, object],
        start_response: rstream_wsgi.StartResponse,
    ) -> list[bytes]:
        assert environ["REQUEST_METHOD"] == "POST"
        assert environ["PATH_INFO"] == "/devices"
        assert environ["QUERY_STRING"] == "online=true"
        assert environ["HTTP_HOST"] == "example.test"
        body = cast(io.BytesIO, environ["wsgi.input"]).read()
        assert body == b"device=cam-1"
        start_response("201 Created", [("content-type", "text/plain")])
        return [b"created"]

    task = asyncio.create_task(rstream_wsgi.serve(app, tunnel))
    try:
        client_writer.write(
            b"POST /devices?online=true HTTP/1.1\r\n"
            b"Host: example.test\r\n"
            b"Content-Length: 12\r\n\r\n"
            b"device=cam-1"
        )
        await client_writer.drain()

        response = await _read_until(client_reader, b"created")
        assert b"HTTP/1.1 201" in response
        assert b"created" in response
    finally:
        task.cancel()
        client_writer.close()
        await asyncio.gather(task, return_exceptions=True)
        await client_writer.wait_closed()


@pytest.mark.asyncio
async def test_wsgi_serve_supports_write_callable() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    def app(
        environ: dict[str, object],
        start_response: rstream_wsgi.StartResponse,
    ) -> list[bytes]:
        write = start_response("200 OK", [("content-type", "text/plain")])
        write(b"chunk-a")
        return [b"chunk-b"]

    task = asyncio.create_task(rstream_wsgi.serve(app, tunnel))
    try:
        client_writer.write(b"GET / HTTP/1.1\r\nHost: example.test\r\n\r\n")
        await client_writer.drain()

        response = await _read_until(client_reader, b"chunk-b")
        assert b"chunk-achunk-b" in response
    finally:
        task.cancel()
        client_writer.close()
        await asyncio.gather(task, return_exceptions=True)
        await client_writer.wait_closed()


@pytest.mark.asyncio
async def test_wsgi_serve_accepts_chunked_request_body() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    def app(
        environ: dict[str, object],
        start_response: rstream_wsgi.StartResponse,
    ) -> list[bytes]:
        body = cast(io.BytesIO, environ["wsgi.input"]).read()
        assert body == b"hello world"
        start_response("200 OK", [("content-type", "text/plain")])
        return [body.upper()]

    task = asyncio.create_task(rstream_wsgi.serve(app, tunnel))
    try:
        client_writer.write(
            b"POST /chunked HTTP/1.1\r\n"
            b"Host: example.test\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n"
            b"5\r\nhello\r\n"
            b"6\r\n world\r\n"
            b"0\r\n\r\n"
        )
        await client_writer.drain()

        response = await _read_until(client_reader, b"HELLO WORLD")
        assert b"HTTP/1.1 200" in response
        assert b"HELLO WORLD" in response
    finally:
        task.cancel()
        client_writer.close()
        await asyncio.gather(task, return_exceptions=True)
        await client_writer.wait_closed()


@pytest.mark.asyncio
async def test_wsgi_serve_times_out_incomplete_request() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    def app(
        environ: dict[str, object],
        start_response: rstream_wsgi.StartResponse,
    ) -> list[bytes]:
        raise AssertionError("WSGI app should not receive incomplete requests")

    task = asyncio.create_task(rstream_wsgi.serve(app, tunnel, read_timeout=0.05))
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
async def test_wsgi_serve_returns_500_on_application_error() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    def app(
        environ: dict[str, object],
        start_response: rstream_wsgi.StartResponse,
    ) -> list[bytes]:
        raise RuntimeError("boom")

    task = asyncio.create_task(rstream_wsgi.serve(app, tunnel))
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
async def test_wsgi_serve_rejects_oversized_body() -> None:
    tunnel, client_reader, client_writer = await _one_stream_tunnel()

    def app(
        environ: dict[str, object],
        start_response: rstream_wsgi.StartResponse,
    ) -> list[bytes]:
        raise AssertionError("WSGI app should not receive oversized payloads")

    task = asyncio.create_task(rstream_wsgi.serve(app, tunnel, max_body_size=4))
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
async def test_wsgi_serve_rejects_invalid_limits() -> None:
    tunnel = cast(rstream.BytestreamTunnel, object())

    def app(
        environ: dict[str, object],
        start_response: rstream_wsgi.StartResponse,
    ) -> list[bytes]:
        return []

    with pytest.raises(ValueError, match="max_header_size"):
        await rstream_wsgi.serve(app, tunnel, max_header_size=0)

    with pytest.raises(ValueError, match="max_body_size"):
        await rstream_wsgi.serve(app, tunnel, max_body_size=-1)

    with pytest.raises(ValueError, match="read_timeout"):
        await rstream_wsgi.serve(app, tunnel, read_timeout=0)


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
