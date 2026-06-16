"""WSGI helpers for serving Python web applications through a tunnel."""

from __future__ import annotations

import asyncio
import io
import sys
from collections.abc import Callable, Iterable
from types import TracebackType
from typing import Protocol
from urllib.parse import unquote, urlsplit

import h11

from rstream.stream import RstreamStream
from rstream.tunnel import BytestreamTunnel

WSGIHeader = tuple[str, str]
WSGIWrite = Callable[[bytes], object]
WSGIExcInfo = tuple[type[BaseException], BaseException, TracebackType]


class StartResponse(Protocol):
    """WSGI start_response callable protocol."""

    def __call__(
        self,
        status: str,
        headers: list[WSGIHeader],
        exc_info: WSGIExcInfo | None = None,
    ) -> WSGIWrite: ...


WSGIApp = Callable[[dict[str, object], StartResponse], Iterable[bytes]]


async def serve(
    app: WSGIApp,
    tunnel: BytestreamTunnel,
    *,
    max_header_size: int = 64 * 1024,
    max_body_size: int = 16 * 1024 * 1024,
    read_timeout: float | None = 30.0,
) -> None:
    """Serve a WSGI app directly on accepted rstream tunnel streams."""

    _validate_limits(max_header_size, max_body_size, read_timeout)
    tasks: set[asyncio.Task[None]] = set()
    try:
        async for stream in tunnel:
            task = asyncio.create_task(
                _serve_stream(
                    app,
                    stream,
                    max_header_size,
                    max_body_size,
                    read_timeout,
                )
            )
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _serve_stream(
    app: WSGIApp,
    stream: RstreamStream,
    max_header_size: int,
    max_body_size: int,
    read_timeout: float | None,
) -> None:
    conn = h11.Connection(h11.SERVER, max_incomplete_event_size=max_header_size)
    request: h11.Request | None = None
    body = bytearray()
    try:
        while True:
            event = conn.next_event()
            if event is h11.NEED_DATA:
                data = await _read(stream, read_timeout)
                if data == b"":
                    await _send_response(conn, stream, 400, [], [b"Bad request."])
                    return
                conn.receive_data(data)
                continue
            if isinstance(event, h11.Request):
                request = event
                continue
            if isinstance(event, h11.Data):
                body.extend(event.data)
                if len(body) > max_body_size:
                    await _send_response(conn, stream, 413, [], [b"Payload too large."])
                    return
                continue
            if isinstance(event, h11.EndOfMessage):
                break
            if isinstance(event, h11.ConnectionClosed):
                return
        if request is None:
            await _send_response(conn, stream, 400, [], [b"Bad request."])
            return
        environ = _environ_from_request(request, bytes(body))
        status, headers, chunks = await asyncio.to_thread(_run_wsgi, app, environ)
        await _send_response(conn, stream, status, headers, chunks)
    except h11.RemoteProtocolError:
        await _send_response(conn, stream, 400, [], [b"Bad request."])
    except asyncio.TimeoutError:
        await _send_response(conn, stream, 408, [], [b"Request timeout."])
    except Exception:
        await _send_response(conn, stream, 500, [], [b"Internal server error."])
    finally:
        stream.close()
        await stream.wait_closed()


def _run_wsgi(
    app: WSGIApp,
    environ: dict[str, object],
) -> tuple[int, list[WSGIHeader], list[bytes]]:
    status_holder: list[str] = []
    headers_holder: list[WSGIHeader] = []
    write_chunks: list[bytes] = []

    def write(data: bytes) -> object:
        if data:
            write_chunks.append(data)
        return None

    def start_response(
        status: str,
        headers: list[WSGIHeader],
        exc_info: WSGIExcInfo | None = None,
    ) -> WSGIWrite:
        if exc_info is not None:
            _, error, _ = exc_info
            raise error
        status_holder.append(status)
        headers_holder.extend(headers)
        return write

    result = app(environ, start_response)
    try:
        chunks = [chunk for chunk in result if chunk]
    finally:
        close = getattr(result, "close", None)
        if callable(close):
            close()
    status_text = status_holder[0] if status_holder else "500 Internal Server Error"
    return int(status_text.split(" ", 1)[0]), headers_holder, write_chunks + chunks


async def _send_response(
    conn: h11.Connection,
    stream: RstreamStream,
    status: int,
    headers: list[WSGIHeader],
    chunks: list[bytes],
) -> None:
    body_length = sum(len(chunk) for chunk in chunks)
    raw_headers = [
        (name.lower().encode(), value.encode())
        for name, value in headers
        if name.lower() not in {"connection", "content-length", "transfer-encoding"}
    ]
    raw_headers.append((b"content-length", str(body_length).encode()))
    raw_headers.append((b"connection", b"close"))
    stream.write(conn.send(h11.Response(status_code=status, headers=raw_headers)))
    for chunk in chunks:
        stream.write(conn.send(h11.Data(data=chunk)))
    stream.write(conn.send(h11.EndOfMessage()))
    await stream.drain()


def _environ_from_request(
    request: h11.Request,
    body: bytes,
) -> dict[str, object]:
    target = request.target
    parsed = urlsplit(target.decode("ascii", errors="surrogateescape"))
    headers = tuple((name.lower(), value) for name, value in request.headers)
    host, port = _host_port(headers)
    environ: dict[str, object] = {
        "REQUEST_METHOD": request.method.decode(),
        "SCRIPT_NAME": "",
        "PATH_INFO": unquote(parsed.path or "/"),
        "QUERY_STRING": parsed.query,
        "SERVER_NAME": host,
        "SERVER_PORT": "" if port is None else str(port),
        "SERVER_PROTOCOL": f"HTTP/{request.http_version.decode()}",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "https",
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    for name, value in headers:
        key = "HTTP_" + name.decode().upper().replace("-", "_")
        if key == "HTTP_CONTENT_LENGTH":
            environ["CONTENT_LENGTH"] = value.decode()
        elif key == "HTTP_CONTENT_TYPE":
            environ["CONTENT_TYPE"] = value.decode()
        else:
            environ[key] = value.decode()
    return environ


def _host_port(headers: Iterable[tuple[bytes, bytes]]) -> tuple[str, int | None]:
    for name, value in headers:
        if name != b"host":
            continue
        raw = value.decode("ascii", errors="ignore")
        if ":" not in raw:
            return raw, None
        host, port_text = raw.rsplit(":", 1)
        try:
            return host, int(port_text)
        except ValueError:
            return raw, None
    return "", None


async def _read(stream: RstreamStream, timeout: float | None) -> bytes:
    if timeout is None:
        return await stream.read(64 * 1024)
    return await asyncio.wait_for(stream.read(64 * 1024), timeout=timeout)


def _validate_limits(
    max_header_size: int,
    max_body_size: int,
    read_timeout: float | None,
) -> None:
    if max_header_size <= 0:
        raise ValueError("max_header_size must be greater than zero")
    if max_body_size < 0:
        raise ValueError("max_body_size must not be negative")
    if read_timeout is not None and read_timeout <= 0:
        raise ValueError("read_timeout must be greater than zero")
