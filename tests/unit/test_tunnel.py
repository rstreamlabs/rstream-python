from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import cast

import pytest

from rstream.errors import ProtocolError, RstreamRuntimeError
from rstream.stream import RstreamStream
from rstream.tunnel import BytestreamTunnel, format_forwarding_address
from rstream.types import TunnelProperties


def test_format_forwarding_address_for_published_http_tunnel() -> None:
    address = format_forwarding_address(
        TunnelProperties(
            id="tun_123",
            protocol="http",
            hostname="api.example.test",
            port=443,
        )
    )

    assert address == "https://api.example.test"


def test_format_forwarding_address_includes_non_default_port() -> None:
    address = format_forwarding_address(
        TunnelProperties(
            id="tun_123",
            protocol="tls",
            hostname="tls.example.test",
            port=8443,
        )
    )

    assert address == "tls.example.test:8443 (tls)"


def test_format_forwarding_address_for_published_tcp_tunnel() -> None:
    address = format_forwarding_address(
        TunnelProperties(
            id="tun_123",
            protocol="tcp",
            hostname="tcp.example.test",
            port=10042,
        )
    )

    assert address == "tcp.example.test:10042 (tcp)"


def test_format_forwarding_address_uses_private_name_or_id() -> None:
    assert (
        format_forwarding_address(TunnelProperties(id="tun_123", name="private-api"))
        == "rstrm://private-api (unpublished)"
    )
    assert (
        format_forwarding_address(TunnelProperties(id="tun_123"))
        == "rstrm://tun_123 (unpublished)"
    )


def test_format_forwarding_address_rejects_empty_properties() -> None:
    with pytest.raises(RstreamRuntimeError, match="Invalid tunnel properties"):
        format_forwarding_address(TunnelProperties())


def test_tunnel_requires_engine_id() -> None:
    with pytest.raises(ProtocolError, match="tunnel ID"):
        BytestreamTunnel(_Control(), TunnelProperties())


@pytest.mark.asyncio
async def test_tunnel_close_delegates_to_control_channel() -> None:
    control = _Control()
    tunnel = BytestreamTunnel(control, TunnelProperties(id="tun_123"))

    await tunnel.close()

    assert control.closed_tunnels == ["tun_123"]


@pytest.mark.asyncio
async def test_tunnel_close_waits_for_forwarders() -> None:
    control = _ClosingControl()
    tunnel = BytestreamTunnel(control, TunnelProperties(id="tun_123"))
    control.tunnel = tunnel
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def forwarder() -> None:
        started.set()
        try:
            await asyncio.Future()
        finally:
            await asyncio.sleep(0)
            stopped.set()

    task = asyncio.create_task(forwarder())
    tunnel._forward_tasks.add(task)
    task.add_done_callback(tunnel._forward_tasks.discard)
    await started.wait()

    await tunnel.close()

    assert stopped.is_set()
    assert task.done()


@pytest.mark.asyncio
async def test_tunnel_accepts_delivered_stream() -> None:
    stream = _stream_double()
    tunnel = BytestreamTunnel(_Control(), TunnelProperties(id="tun_123"))

    assert tunnel.deliver(stream) is True

    accepted = await tunnel.accept()
    assert accepted is stream


@pytest.mark.asyncio
async def test_tunnel_rejects_delivery_after_close() -> None:
    stream = _stream_double()
    tunnel = BytestreamTunnel(_Control(), TunnelProperties(id="tun_123"))
    tunnel.on_close()

    assert tunnel.deliver(stream) is False
    assert stream.writer.is_closing()


@pytest.mark.asyncio
async def test_tunnel_async_iterator_stops_after_close() -> None:
    tunnel = BytestreamTunnel(_Control(), TunnelProperties(id="tun_123"))
    tunnel.on_close()

    with pytest.raises(StopAsyncIteration):
        await tunnel.__anext__()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("host", "port"),
    [
        ("", 8000),
        ("   ", 8000),
        ("127.0.0.1", 0),
        ("127.0.0.1", 65_536),
    ],
)
async def test_tunnel_forward_to_rejects_invalid_local_endpoint(
    host: str,
    port: int,
) -> None:
    tunnel = BytestreamTunnel(_Control(), TunnelProperties(id="tun_123"))

    with pytest.raises(RstreamRuntimeError) as exc:
        await tunnel.forward_to(host, port)

    assert exc.value.code == "ERR_RSTREAM_INVALID_LOCAL_ENDPOINT"


@dataclass
class _Control:
    closed_tunnels: list[str] = field(default_factory=list)

    async def close_tunnel(self, tunnel_id: str) -> None:
        self.closed_tunnels.append(tunnel_id)


@dataclass
class _ClosingControl(_Control):
    tunnel: BytestreamTunnel | None = None

    async def close_tunnel(self, tunnel_id: str) -> None:
        await super().close_tunnel(tunnel_id)
        assert self.tunnel is not None
        self.tunnel.on_close()


class _WriterDouble:
    def __init__(self) -> None:
        self._closing = False

    def close(self) -> None:
        self._closing = True

    def is_closing(self) -> bool:
        return self._closing


class _StreamDouble:
    def __init__(self) -> None:
        self.writer = _WriterDouble()

    def close(self) -> None:
        self.writer.close()


def _stream_double() -> RstreamStream:
    return cast(RstreamStream, _StreamDouble())
