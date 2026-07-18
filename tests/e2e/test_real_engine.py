from __future__ import annotations

import asyncio
import os
import ssl
import uuid
from socket import socket as Socket
from typing import cast
from urllib.request import urlopen

import pytest

import rstream
import rstream.asgi as rstream_asgi
import rstream.wsgi as rstream_wsgi


@pytest.mark.asyncio
async def test_real_engine_private_bytestream_matrix() -> None:
    if not real_engine_enabled():
        pytest.skip(
            "Set RSTREAM_PYTHON_E2E=1 or RSTREAM_PYTHON_E2E_ENGINE to run "
            "real-engine e2e tests."
        )

    tunnel_name = f"python-e2e-{uuid.uuid4().hex[:12]}"
    client = real_engine_client(zero_rtt=False)

    async with client, await client.connect() as control:
        tunnel = await control.create_tunnel(
            labels={"sdk": "python", "test": "real-engine-e2e"},
            name=tunnel_name,
            publish=False,
        )
        try:
            assert control.server_details is not None
            assert tunnel.id

            for target in (tunnel_name, tunnel.id):
                for zero_rtt in (False, True):
                    responder = asyncio.create_task(
                        echo_one_stream(tunnel, b"ping", b"PONG")
                    )
                    try:
                        await assert_private_round_trip(
                            client,
                            target,
                            zero_rtt=zero_rtt,
                            request=b"ping",
                            response=b"PONG",
                        )
                    finally:
                        responder.cancel()
                        await asyncio.gather(responder, return_exceptions=True)

            responder = asyncio.create_task(echo_n_streams(tunnel, 5))
            try:
                await asyncio.gather(
                    *(
                        assert_private_round_trip(
                            client,
                            tunnel_name,
                            zero_rtt=index % 2 == 0,
                            request=f"msg{index}".encode(),
                            response=f"MSG{index}".encode(),
                        )
                        for index in range(5)
                    )
                )
            finally:
                responder.cancel()
                await asyncio.gather(responder, return_exceptions=True)
        finally:
            await tunnel.close()


@pytest.mark.asyncio
async def test_real_engine_published_http_tunnel() -> None:
    if (
        not real_engine_enabled()
        or os.environ.get("RSTREAM_PYTHON_E2E_PUBLISHED") != "1"
    ):
        pytest.skip(
            "Set RSTREAM_PYTHON_E2E=1 and RSTREAM_PYTHON_E2E_PUBLISHED=1 to "
            "run published-tunnel e2e tests."
        )

    local_server = await asyncio.start_server(handle_http_hostname, "127.0.0.1", 0)
    forward_task: asyncio.Task[None] | None = None
    client = real_engine_client(zero_rtt=False)
    try:
        local_host, local_port = server_address(local_server)
        async with client, await client.connect() as control:
            tunnel = await control.create_tunnel(
                labels={"sdk": "python", "test": "published-http-e2e"},
                protocol="http",
                http_version="http/1.1",
                publish=True,
            )
            forward_task = asyncio.create_task(
                tunnel.forward_to(local_host, local_port)
            )
            try:
                body = await asyncio.to_thread(
                    fetch_insecure,
                    tunnel.forwarding_address,
                )
                assert body == b"rstream-python-e2e"
            finally:
                await tunnel.close()
                forward_task.cancel()
                await asyncio.gather(forward_task, return_exceptions=True)
    finally:
        local_server.close()
        await local_server.wait_closed()


@pytest.mark.asyncio
async def test_real_engine_published_tcp_tunnel() -> None:
    if (
        not real_engine_enabled()
        or os.environ.get("RSTREAM_PYTHON_E2E_PUBLISHED_TCP") != "1"
    ):
        pytest.skip(
            "Set RSTREAM_PYTHON_E2E=1 and RSTREAM_PYTHON_E2E_PUBLISHED_TCP=1 "
            "to run published-TCP e2e tests."
        )

    local_server = await asyncio.start_server(handle_tcp_echo, "127.0.0.1", 0)
    forward_task: asyncio.Task[None] | None = None
    client = real_engine_client(zero_rtt=False)
    try:
        local_host, local_port = server_address(local_server)
        async with client, await client.connect() as control:
            tunnel = await control.create_tunnel(
                labels={"sdk": "python", "test": "published-tcp-e2e"},
                protocol="tcp",
            )
            assert tunnel.properties.hostname is not None
            assert tunnel.properties.port is not None
            forward_task = asyncio.create_task(
                tunnel.forward_to(local_host, local_port)
            )
            connect_host = os.environ.get(
                "RSTREAM_PYTHON_E2E_PUBLISHED_CONNECT_HOST",
                tunnel.properties.hostname,
            )
            try:
                reader, writer = await asyncio.open_connection(
                    connect_host,
                    tunnel.properties.port,
                )
                try:
                    writer.write(b"ping")
                    await writer.drain()
                    assert await reader.readexactly(4) == b"PING"
                finally:
                    writer.close()
                    await writer.wait_closed()
            finally:
                await tunnel.close()
                forward_task.cancel()
                await asyncio.gather(forward_task, return_exceptions=True)
    finally:
        local_server.close()
        await local_server.wait_closed()


@pytest.mark.asyncio
async def test_real_engine_private_wsgi_tunnel() -> None:
    if not real_engine_enabled():
        pytest.skip(
            "Set RSTREAM_PYTHON_E2E=1 or RSTREAM_PYTHON_E2E_ENGINE to run "
            "real-engine e2e tests."
        )

    tunnel_name = f"python-wsgi-{uuid.uuid4().hex[:12]}"
    client = real_engine_client(zero_rtt=False)

    def app(
        environ: dict[str, object],
        start_response: rstream_wsgi.StartResponse,
    ) -> list[bytes]:
        assert environ["PATH_INFO"] == "/health"
        body = b"rstream-python-wsgi-e2e"
        start_response("200 OK", [("content-type", "text/plain")])
        return [body]

    async with client, await client.connect() as control:
        tunnel = await control.create_tunnel(
            labels={"sdk": "python", "test": "private-wsgi-e2e"},
            name=tunnel_name,
            publish=False,
        )
        serving = asyncio.create_task(rstream_wsgi.serve(app, tunnel))
        try:
            body = await private_http_get(client, tunnel_name, "/health")
            assert body.endswith(b"rstream-python-wsgi-e2e")
        finally:
            await tunnel.close()
            serving.cancel()
            await asyncio.gather(serving, return_exceptions=True)


@pytest.mark.asyncio
async def test_real_engine_published_asgi_tunnel() -> None:
    if (
        not real_engine_enabled()
        or os.environ.get("RSTREAM_PYTHON_E2E_PUBLISHED") != "1"
    ):
        pytest.skip(
            "Set RSTREAM_PYTHON_E2E=1 and RSTREAM_PYTHON_E2E_PUBLISHED=1 to "
            "run published-tunnel e2e tests."
        )

    async def app(
        scope: rstream_asgi.ASGIScope,
        receive: rstream_asgi.Receive,
        send: rstream_asgi.Send,
    ) -> None:
        assert scope["path"] == "/health"
        body = b"rstream-python-asgi-e2e"
        await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": body})

    client = real_engine_client(zero_rtt=False)
    async with client, await client.connect() as control:
        tunnel = await control.create_tunnel(
            labels={"sdk": "python", "test": "published-asgi-e2e"},
            protocol="http",
            http_version="http/1.1",
            publish=True,
        )
        serving = asyncio.create_task(rstream_asgi.serve(app, tunnel))
        try:
            body = await asyncio.to_thread(
                fetch_insecure,
                tunnel.forwarding_address + "/health",
            )
            assert body == b"rstream-python-asgi-e2e"
        finally:
            await tunnel.close()
            serving.cancel()
            await asyncio.gather(serving, return_exceptions=True)


async def assert_private_round_trip(
    client: rstream.Client,
    target: str,
    *,
    zero_rtt: bool,
    request: bytes,
    response: bytes,
) -> None:
    async with await client.dial(target, zero_rtt=zero_rtt) as stream:
        stream.write(request)
        await stream.drain()
        assert await stream.readexactly(len(response)) == response


async def private_http_get(
    client: rstream.Client,
    target: str,
    path: str,
) -> bytes:
    async with await client.dial(target, zero_rtt=False) as stream:
        request = f"GET {path} HTTP/1.1\r\nHost: {target}\r\nConnection: close\r\n\r\n"
        stream.write(request.encode())
        await stream.drain()
        return await stream.read()


async def echo_one_stream(
    tunnel: rstream.BytestreamTunnel,
    request: bytes,
    response: bytes,
) -> None:
    async with await tunnel.accept() as stream:
        assert await stream.readexactly(len(request)) == request
        stream.write(response)
        await stream.drain()


async def echo_n_streams(tunnel: rstream.BytestreamTunnel, count: int) -> None:
    tasks: list[asyncio.Task[None]] = []
    try:
        for _ in range(count):
            stream = await tunnel.accept()
            tasks.append(asyncio.create_task(echo_uppercase(stream)))
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def echo_uppercase(stream: rstream.RstreamStream) -> None:
    async with stream:
        payload = await stream.readexactly(4)
        stream.write(payload.upper())
        await stream.drain()


async def handle_http_hostname(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    try:
        await reader.readuntil(b"\r\n\r\n")
        body = b"rstream-python-e2e"
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            + f"content-length: {len(body)}\r\n".encode()
            + b"content-type: text/plain\r\n\r\n"
            + body
        )
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def handle_tcp_echo(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    try:
        payload = await reader.readexactly(4)
        writer.write(payload.upper())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


def fetch_insecure(url: str) -> bytes:
    context = ssl._create_unverified_context()
    with urlopen(url, context=context, timeout=10) as response:
        return cast(bytes, response.read())


def real_engine_enabled() -> bool:
    return (
        os.environ.get("RSTREAM_PYTHON_E2E") == "1"
        or os.environ.get("RSTREAM_PYTHON_E2E_ENGINE") is not None
    )


def real_engine_client(*, zero_rtt: bool) -> rstream.Client:
    engine = os.environ.get("RSTREAM_PYTHON_E2E_ENGINE")
    if engine is None:
        return rstream.Client.from_env(zero_rtt=zero_rtt)
    token = os.environ.get("RSTREAM_PYTHON_E2E_TOKEN")
    ca_file = os.environ.get("RSTREAM_PYTHON_E2E_CA_FILE")
    insecure_skip_verify = os.environ.get("RSTREAM_PYTHON_E2E_TLS_INSECURE") == "1"
    server_name = os.environ.get("RSTREAM_PYTHON_E2E_SERVER_NAME")
    tls = (
        rstream.TLSOptions(
            ca_file=ca_file,
            insecure_skip_verify=insecure_skip_verify,
            server_name=server_name,
        )
        if ca_file or insecure_skip_verify or server_name
        else None
    )
    return rstream.Client(
        engine=engine,
        no_token=token is None,
        read_config_file=False,
        tls=tls,
        token=token,
        zero_rtt=zero_rtt,
    )


def server_address(server: asyncio.AbstractServer) -> tuple[str, int]:
    sockets_object = getattr(server, "sockets", None)
    assert sockets_object is not None
    sockets = cast(list[Socket], sockets_object)
    host, port = sockets[0].getsockname()[:2]
    return str(host), int(port)
