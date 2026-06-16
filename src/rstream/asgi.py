"""ASGI helpers for serving Python web applications through a tunnel."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import unquote, urlsplit

import h11

from rstream.stream import RstreamStream
from rstream.tunnel import BytestreamTunnel

ASGIScope = dict[str, object]
ASGIMessage = dict[str, object]
Receive = Callable[[], Awaitable[ASGIMessage]]
Send = Callable[[ASGIMessage], Awaitable[None]]


class ASGIApp(Protocol):
    """Callable ASGI application protocol."""

    def __call__(
        self,
        scope: ASGIScope,
        receive: Receive,
        send: Send,
    ) -> Awaitable[None]: ...


async def serve(
    app: ASGIApp,
    tunnel: BytestreamTunnel,
    *,
    max_header_size: int = 64 * 1024,
    max_body_size: int = 16 * 1024 * 1024,
    read_timeout: float | None = 30.0,
) -> None:
    """Serve an ASGI app directly on accepted rstream tunnel streams.

    The helper is stream-native: it does not start a local Uvicorn server and
    does not forward through a loopback port. Each accepted HTTP/1.1 stream is
    parsed and dispatched to the ASGI app in-process.
    """

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
    app: ASGIApp,
    stream: RstreamStream,
    max_header_size: int,
    max_body_size: int,
    read_timeout: float | None,
) -> None:
    conn = h11.Connection(h11.SERVER, max_incomplete_event_size=max_header_size)
    request_queue: asyncio.Queue[ASGIMessage] = asyncio.Queue()
    app_task: asyncio.Task[None] | None = None
    response_state = _ResponseState()
    body_size = 0
    try:
        while True:
            event = conn.next_event()
            if event is h11.NEED_DATA:
                if app_task is not None and app_task.done() and response_state.complete:
                    await app_task
                    return
                data = await _read(stream, read_timeout)
                if data == b"":
                    if app_task is None:
                        await _send_simple_response(conn, stream, 400, b"Bad request.")
                    else:
                        await request_queue.put({"type": "http.disconnect"})
                    return
                conn.receive_data(data)
                continue
            if isinstance(event, h11.Request):
                if app_task is not None:
                    await _send_simple_response(conn, stream, 400, b"Bad request.")
                    return
                app_task = asyncio.create_task(
                    _dispatch_asgi(
                        app,
                        conn,
                        stream,
                        event,
                        request_queue,
                        response_state,
                    )
                )
                continue
            if isinstance(event, h11.Data):
                if app_task is None:
                    await _send_simple_response(conn, stream, 400, b"Bad request.")
                    return
                body_size += len(event.data)
                if body_size > max_body_size:
                    await _reject_running_app(
                        conn,
                        stream,
                        request_queue,
                        app_task,
                        response_state,
                        413,
                        b"Payload too large.",
                    )
                    return
                await request_queue.put(
                    {
                        "type": "http.request",
                        "body": bytes(event.data),
                        "more_body": True,
                    }
                )
                continue
            if isinstance(event, h11.EndOfMessage):
                if app_task is None:
                    await _send_simple_response(conn, stream, 400, b"Bad request.")
                    return
                await request_queue.put(
                    {"type": "http.request", "body": b"", "more_body": False}
                )
                await app_task
                break
            if isinstance(event, h11.ConnectionClosed):
                if app_task is not None:
                    await request_queue.put({"type": "http.disconnect"})
                return
    except asyncio.TimeoutError:
        if app_task is not None:
            await request_queue.put({"type": "http.disconnect"})
        if not response_state.started:
            await _send_simple_response(conn, stream, 408, b"Request timeout.")
    except h11.RemoteProtocolError:
        await _send_simple_response(conn, stream, 400, b"Bad request.")
    except Exception:
        if not response_state.started:
            await _send_simple_response(conn, stream, 500, b"Internal server error.")
    finally:
        if app_task is not None and not app_task.done():
            app_task.cancel()
            await asyncio.gather(app_task, return_exceptions=True)
        stream.close()
        await stream.wait_closed()


async def _dispatch_asgi(
    app: ASGIApp,
    conn: h11.Connection,
    stream: RstreamStream,
    request: h11.Request,
    request_queue: asyncio.Queue[ASGIMessage],
    response_state: _ResponseState,
) -> None:
    request_complete = False
    scope = _scope_from_request(request)

    async def receive() -> ASGIMessage:
        nonlocal request_complete
        if request_complete:
            return {"type": "http.disconnect"}
        message = await request_queue.get()
        if message.get("type") != "http.request":
            request_complete = True
            return message
        if not bool(message.get("more_body", False)):
            request_complete = True
        return message

    async def send(message: ASGIMessage) -> None:
        message_type = message.get("type")
        if message_type == "http.response.start":
            if response_state.started:
                raise RuntimeError("ASGI response already started.")
            status = _int_value(message.get("status"), 500)
            headers = _headers_from_asgi(message.get("headers"))
            stream.write(
                conn.send(h11.Response(status_code=status, headers=list(headers)))
            )
            await stream.drain()
            response_state.started = True
            return
        if message_type == "http.response.body":
            if response_state.complete:
                raise RuntimeError("ASGI response already completed.")
            if not response_state.started:
                stream.write(conn.send(h11.Response(status_code=200, headers=[])))
                response_state.started = True
            payload = _bytes_value(message.get("body"))
            if payload:
                stream.write(conn.send(h11.Data(data=payload)))
            more_body = bool(message.get("more_body", False))
            if not more_body:
                stream.write(conn.send(h11.EndOfMessage()))
                response_state.complete = True
            await stream.drain()

    try:
        await app(scope, receive, send)
        if not response_state.complete:
            if not response_state.started:
                stream.write(conn.send(h11.Response(status_code=204, headers=[])))
                response_state.started = True
            stream.write(conn.send(h11.EndOfMessage()))
            response_state.complete = True
            await stream.drain()
    except Exception:
        if response_state.started:
            raise
        await _send_simple_response(conn, stream, 500, b"Internal server error.")
        response_state.started = True
        response_state.complete = True


@dataclass
class _ResponseState:
    started: bool = False
    complete: bool = False


async def _send_simple_response(
    conn: h11.Connection,
    stream: RstreamStream,
    status: int,
    body: bytes,
) -> None:
    headers = [(b"content-length", str(len(body)).encode())]
    stream.write(conn.send(h11.Response(status_code=status, headers=headers)))
    if body:
        stream.write(conn.send(h11.Data(data=body)))
    stream.write(conn.send(h11.EndOfMessage()))
    await stream.drain()


async def _reject_running_app(
    conn: h11.Connection,
    stream: RstreamStream,
    request_queue: asyncio.Queue[ASGIMessage],
    app_task: asyncio.Task[None],
    response_state: _ResponseState,
    status: int,
    body: bytes,
) -> None:
    await request_queue.put({"type": "http.disconnect"})
    app_task.cancel()
    await asyncio.gather(app_task, return_exceptions=True)
    if not response_state.started:
        await _send_simple_response(conn, stream, status, body)


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


def _scope_from_request(request: h11.Request) -> ASGIScope:
    target = request.target
    parsed = urlsplit(target.decode("ascii", errors="surrogateescape"))
    headers = tuple((name.lower(), value) for name, value in request.headers)
    host, port = _host_port(headers)
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.5"},
        "http_version": request.http_version.decode(),
        "method": request.method.decode(),
        "scheme": "https",
        "path": unquote(parsed.path or "/"),
        "raw_path": (parsed.path or "/").encode(),
        "query_string": parsed.query.encode(),
        "headers": headers,
        "client": None,
        "server": (host, port),
        "root_path": "",
    }


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


def _headers_from_asgi(value: object) -> tuple[tuple[bytes, bytes], ...]:
    if not isinstance(value, Iterable):
        return ()
    headers: list[tuple[bytes, bytes]] = []
    for item in value:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], bytes)
            and isinstance(item[1], bytes)
        ):
            headers.append((item[0], item[1]))
    return tuple(headers)


def _bytes_value(value: object) -> bytes:
    return value if isinstance(value, bytes) else b""


def _int_value(value: object, fallback: int) -> int:
    return value if isinstance(value, int) else fallback
