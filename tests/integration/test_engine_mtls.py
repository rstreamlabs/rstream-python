from __future__ import annotations

import asyncio
import ssl
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import trustme
from aiohttp import web

from rstream.client import Client
from rstream.config import TLSOptions
from rstream.engine_discovery import EngineAPIDiscovery, _target
from rstream.errors import RstreamRuntimeError


@pytest.fixture
async def engine_pair(
    tmp_path: Path,
) -> AsyncIterator[tuple[str, TLSOptions, dict[str, int]]]:
    ca = trustme.CA()
    ca.cert_pem.write_to_path(tmp_path / "ca.pem")
    certificate = ca.issue_cert("device.test")
    certificate.cert_chain_pems[0].write_to_path(tmp_path / "client.pem")
    certificate.private_key_pem.write_to_path(tmp_path / "client.key")
    server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ca.issue_cert("localhost").configure_cert(server_tls)
    ca.configure_trust(server_tls)
    server_tls.verify_mode = ssl.CERT_OPTIONAL
    calls = {"discovery": 0, "authenticated": 0}

    async def authenticated(request: web.Request) -> web.StreamResponse:
        assert request.transport is not None
        assert request.transport.get_extra_info("peercert")
        assert "Authorization" not in request.headers
        calls["authenticated"] += 1
        if request.path == "/api/sse":
            return web.Response(
                text='data: {"type":"client.connected"}\n\n',
                content_type="text/event-stream",
            )
        if request.path == "/api/websocket":
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({"type": "client.connected"})
            await ws.close()
            return ws
        return web.json_response([{"id": "device"}])

    api = web.Application()
    api.router.add_get("/api/{path}", authenticated)
    api_runner = web.AppRunner(api)
    await api_runner.setup()
    api_site = web.TCPSite(api_runner, "127.0.0.1", 0, ssl_context=server_tls)
    await api_site.start()
    api_port = api_runner.addresses[0][1]

    async def discover(request: web.Request) -> web.Response:
        assert request.transport is not None
        assert not request.transport.get_extra_info("peercert")
        assert "Authorization" not in request.headers
        assert "Cookie" not in request.headers
        calls["discovery"] += 1
        await asyncio.sleep(0.02)
        return web.json_response(
            {
                "version": 1,
                "projectEndpoint": "localhost",
                "mtlsApiUrl": f"https://localhost:{api_port}/api",
                "capabilities": ["engine-api-mtls"],
            },
            headers={"Cache-Control": "public, max-age=3600"},
        )

    public = web.Application()
    public.router.add_get("/.well-known/rstream/engine", discover)
    public_runner = web.AppRunner(public)
    await public_runner.setup()
    public_site = web.TCPSite(public_runner, "127.0.0.1", 0, ssl_context=server_tls)
    await public_site.start()
    public_port = public_runner.addresses[0][1]
    try:
        yield (
            f"localhost:{public_port}",
            TLSOptions(
                ca_file=str(tmp_path / "ca.pem"),
                cert_file=str(tmp_path / "client.pem"),
                key_file=str(tmp_path / "client.key"),
            ),
            calls,
        )
    finally:
        await public_runner.cleanup()
        await api_runner.cleanup()


async def test_mtls_inventory_and_watch_reuse_anonymous_discovery(
    engine_pair: tuple[str, TLSOptions, dict[str, int]],
) -> None:
    engine, tls, calls = engine_pair
    async with Client(engine=engine, tls=tls, read_config_file=False) as client:
        inventories = await asyncio.gather(*(client.list_clients() for _ in range(12)))
        assert all(items[0]["id"] == "device" for items in inventories)
        for events in [
            client.watch(transport="sse"),
            client.watch(transport="websocket"),
        ]:
            async with events:
                assert (
                    await asyncio.wait_for(anext(events), 5)
                ).type == "client.connected"
        assert calls == {"discovery": 1, "authenticated": 14}
    with pytest.raises(RstreamRuntimeError, match="closed"):
        await client.list_clients()


async def test_discovery_verifies_tls_and_isolates_waiter_cancellation(
    engine_pair: tuple[str, TLSOptions, dict[str, int]],
) -> None:
    engine, tls, calls = engine_pair
    discovery = EngineAPIDiscovery()
    first = asyncio.create_task(discovery.resolve(engine, tls))
    second = asyncio.create_task(discovery.resolve(engine, tls))
    await asyncio.sleep(0.005)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert (await second).startswith("localhost:")
    assert calls["discovery"] == 1
    await discovery.close()
    import httpx

    untrusted = EngineAPIDiscovery()
    try:
        with pytest.raises(httpx.ConnectError):
            await untrusted.resolve(engine, TLSOptions(insecure_skip_verify=True))
    finally:
        await untrusted.close()


async def test_close_cancels_discovery_and_joins_its_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def pending_request(
        self: EngineAPIDiscovery, engine: str, tls: TLSOptions | None
    ) -> str:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
        raise AssertionError("pending discovery should have been cancelled")

    monkeypatch.setattr(EngineAPIDiscovery, "_request", pending_request)
    discovery = EngineAPIDiscovery()
    waiter = asyncio.create_task(discovery.resolve("project.engine.test", None))
    await asyncio.wait_for(started.wait(), 1)
    await discovery.close()
    assert stopped.is_set()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    with pytest.raises(RstreamRuntimeError, match="closed"):
        await discovery.resolve("project.engine.test", None)


@pytest.mark.parametrize(
    "url",
    [
        "http://project.mtls.test/api",
        "https://other.mtls.test/api",
        "https://user@project.mtls.test/api",
        "https://project.mtls.test/api?token=x",
        "https://project.mtls.test/other",
        "https://project.mtls.test:0/api",
    ],
)
def test_discovery_rejects_untrusted_authorities_and_paths(url: str) -> None:
    with pytest.raises(RstreamRuntimeError):
        _target(
            {
                "version": 1,
                "projectEndpoint": "project",
                "mtlsApiUrl": url,
                "capabilities": ["engine-api-mtls"],
            },
            "project.engine.test:443",
        )
