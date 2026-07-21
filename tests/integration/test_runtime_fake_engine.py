from __future__ import annotations

import asyncio
import ssl
from pathlib import Path

import pytest
import trustme
from google.protobuf.wrappers_pb2 import StringValue

import rstream
from rstream._proto import rstream_pb2 as pb
from rstream.protocol import read_message, write_message


@pytest.mark.asyncio
async def test_connect_create_and_close_tunnel(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine)

        async with await client.connect() as control:
            tunnel = await control.create_tunnel(
                protocol="http",
                http_version="http/1.1",
                publish=True,
            )
            assert tunnel.id == "tun_test_1"
            assert tunnel.forwarding_address == "https://test.localhost"
            await tunnel.close()

        assert engine.open_tunnel_requests == 1
        assert engine.close_tunnel_requests == 1


@pytest.mark.asyncio
async def test_published_tcp_options_and_local_validation(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine)

        async with await client.connect() as control:
            tunnel = await control.create_tunnel(
                protocol="tcp",
                port=10042,
                allow_cross_region_routing=True,
            )
            assert tunnel.forwarding_address == "test.localhost:10042 (tcp)"
            assert tunnel.properties.allow_cross_region_routing is True
            with pytest.raises(
                rstream.RstreamRuntimeError, match="do not accept"
            ) as exc:
                await control.create_tunnel(
                    protocol="tcp",
                    hostname="ssh.example.test",
                )
            assert exc.value.code == "ERR_RSTREAM_INVALID_TUNNEL"
            with pytest.raises(
                rstream.RstreamRuntimeError, match="requires protocol='tcp'"
            ) as exc:
                await control.create_tunnel(
                    protocol="http",
                    allow_cross_region_routing=True,
                )
            assert exc.value.code == "ERR_RSTREAM_INVALID_TUNNEL"

        assert engine.open_tunnel_requests == 1


@pytest.mark.asyncio
async def test_dial_private_tunnel_with_and_without_zero_rtt(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine)

        async with await client.dial("private-api", zero_rtt=False) as stream:
            stream.write(b"ping")
            await stream.drain()
            assert await stream.readexactly(4) == b"PONG"

        async with await client.dial("private-api", zero_rtt=True) as stream:
            stream.write(b"ping")
            await stream.drain()
            assert await stream.readexactly(4) == b"PONG"

        assert engine.stream_requests == [
            ("private-api", False),
            ("private-api", True),
        ]


@pytest.mark.asyncio
async def test_control_open_timeout_is_bounded(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        engine.next_control_hang = True
        client = client_for(engine, operation_timeout=0.05)

        with pytest.raises(rstream.RstreamRuntimeError) as exc:
            await client.connect()

        assert exc.value.code == "ERR_RSTREAM_OPERATION_TIMEOUT"


@pytest.mark.asyncio
async def test_open_tunnel_timeout_is_bounded_and_retryable(
    tmp_path: Path,
) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine, operation_timeout=0.05)

        async with await client.connect() as control:
            engine.next_open_tunnel_hang = True

            with pytest.raises(rstream.RstreamRuntimeError) as exc:
                await control.create_tunnel()

            assert exc.value.code == "ERR_RSTREAM_OPERATION_TIMEOUT"

            tunnel = await control.create_tunnel()
            assert tunnel.id == "tun_test_1"

        assert engine.open_tunnel_requests == 2


@pytest.mark.asyncio
async def test_close_tunnel_timeout_is_bounded_and_retryable(
    tmp_path: Path,
) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine, operation_timeout=0.05)

        async with await client.connect() as control:
            tunnel = await control.create_tunnel()
            engine.next_close_tunnel_hang = True

            with pytest.raises(rstream.RstreamRuntimeError) as exc:
                await tunnel.close()

            assert exc.value.code == "ERR_RSTREAM_OPERATION_TIMEOUT"
            assert bool(tunnel.closed) is False

            await tunnel.close()
            assert bool(tunnel.closed) is True
            assert engine.close_tunnel_requests == 2


@pytest.mark.asyncio
async def test_concurrent_close_tunnel_sends_one_request(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine)

        async with await client.connect() as control:
            tunnel = await control.create_tunnel()

            await asyncio.gather(tunnel.close(), tunnel.close(), tunnel.close())

        assert engine.close_tunnel_requests == 1


@pytest.mark.asyncio
async def test_close_control_channel_timeout_is_bounded(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine, operation_timeout=0.05)
        control = await client.connect()
        engine.next_close_control_hang = True

        with pytest.raises(rstream.RstreamRuntimeError) as exc:
            await control.close()

        assert exc.value.code == "ERR_RSTREAM_OPERATION_TIMEOUT"
        assert control.closed


@pytest.mark.asyncio
async def test_stream_handshake_timeout_is_bounded(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        engine.next_stream_hang = True
        client = client_for(engine, operation_timeout=0.05)

        with pytest.raises(rstream.RstreamRuntimeError) as exc:
            await client.dial("private-api", zero_rtt=False)

        assert exc.value.code == "ERR_RSTREAM_OPERATION_TIMEOUT"


@pytest.mark.asyncio
async def test_empty_stream_response_is_protocol_error(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        engine.next_stream_empty_response = True
        client = client_for(engine)

        with pytest.raises(rstream.ProtocolError, match="empty StreamRsp"):
            await client.dial("private-api", zero_rtt=False)


@pytest.mark.asyncio
async def test_proxy_connection_delivery_round_trip(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine, zero_rtt=False)

        async with await client.connect() as control:
            tunnel = await control.create_tunnel()
            response_waiter = asyncio.create_task(
                engine.request_proxy_connection(tunnel.id, "stream_proxy_1")
            )
            app_stream = await asyncio.wait_for(tunnel.accept(), timeout=1)
            engine_stream = await engine.next_proxy_stream()
            response = await response_waiter

            assert response.WhichOneof("payload") == "proxy_conn_rsp"
            assert response.proxy_conn_rsp.stream_id == "stream_proxy_1"
            assert not response.proxy_conn_rsp.HasField("error")

            app_stream.write(b"ping")
            await app_stream.drain()
            assert await engine_stream.readexactly(4) == b"ping"

            engine_stream.write(b"PONG")
            await engine_stream.drain()
            assert await app_stream.readexactly(4) == b"PONG"

            app_stream.close()
            engine_stream.close()
            await asyncio.gather(
                app_stream.wait_closed(),
                engine_stream.wait_closed(),
                return_exceptions=True,
            )


@pytest.mark.asyncio
async def test_proxy_connection_can_dial_ingress_engine(tmp_path: Path) -> None:
    ca = trustme.CA()
    async with (
        await FakeEngine.start(tmp_path, name="owner", ca=ca) as owner,
        await FakeEngine.start(tmp_path, name="ingress", ca=ca) as ingress,
    ):
        client = client_for(owner, token="owner-pat", zero_rtt=False)
        async with await client.connect() as control:
            tunnel = await control.create_tunnel()
            response_waiter = asyncio.create_task(
                owner.request_proxy_connection(
                    tunnel.id,
                    "stream_direct_1",
                    proxy_endpoint=ingress.address,
                )
            )
            app_stream = await asyncio.wait_for(tunnel.accept(), timeout=1)
            ingress_stream = await ingress.next_proxy_stream()
            response = await response_waiter
            assert not response.proxy_conn_rsp.HasField("error")
            assert owner.proxy_requests == []
            assert ingress.proxy_requests == [("stream_direct_1", False)]
            assert ingress.proxy_tokens == ["stream-secret"]
            app_stream.write(b"ping")
            await app_stream.drain()
            assert await ingress_stream.readexactly(4) == b"ping"
            app_stream.close()
            ingress_stream.close()
            await asyncio.gather(
                app_stream.wait_closed(),
                ingress_stream.wait_closed(),
                return_exceptions=True,
            )


@pytest.mark.asyncio
async def test_proxy_redirect_without_stream_secret_is_rejected(tmp_path: Path) -> None:
    ca = trustme.CA()
    async with (
        await FakeEngine.start(tmp_path, name="owner", ca=ca) as owner,
        await FakeEngine.start(tmp_path, name="ingress", ca=ca) as ingress,
    ):
        client = client_for(owner)
        async with await client.connect() as control:
            tunnel = await control.create_tunnel()
            response = await owner.request_proxy_connection(
                tunnel.id,
                "stream_missing_secret",
                proxy_endpoint=ingress.address,
                include_secret=False,
            )
            assert response.proxy_conn_rsp.HasField("error")
            assert "credentials" in response.proxy_conn_rsp.error.message.value
            assert owner.proxy_requests == []
            assert ingress.proxy_requests == []


@pytest.mark.asyncio
async def test_proxy_redirect_with_empty_stream_secret_is_rejected(
    tmp_path: Path,
) -> None:
    ca = trustme.CA()
    async with (
        await FakeEngine.start(tmp_path, name="owner", ca=ca) as owner,
        await FakeEngine.start(tmp_path, name="ingress", ca=ca) as ingress,
    ):
        client = client_for(owner)
        async with await client.connect() as control:
            tunnel = await control.create_tunnel()
            response = await owner.request_proxy_connection(
                tunnel.id,
                "stream_empty_secret",
                proxy_endpoint=ingress.address,
                secret="",
            )
            assert response.proxy_conn_rsp.HasField("error")
            assert "credentials" in response.proxy_conn_rsp.error.message.value
            assert owner.proxy_requests == []
            assert ingress.proxy_requests == []


@pytest.mark.asyncio
async def test_proxy_handshake_timeout_is_reported_to_engine(
    tmp_path: Path,
) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine, operation_timeout=0.05, zero_rtt=False)

        async with await client.connect() as control:
            tunnel = await control.create_tunnel()
            engine.next_proxy_hang = True

            response = await engine.request_proxy_connection(
                tunnel.id,
                "stream_proxy_timeout",
            )

            assert response.WhichOneof("payload") == "proxy_conn_rsp"
            assert response.proxy_conn_rsp.HasField("error")
            assert "Timed out" in response.proxy_conn_rsp.error.message.value


@pytest.mark.asyncio
async def test_done_raises_when_control_transport_fails(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine)
        control = await client.connect()

        await engine.close_control_transport()

        with pytest.raises(asyncio.IncompleteReadError):
            await asyncio.wait_for(control.done(), timeout=1)


@pytest.mark.asyncio
async def test_client_close_closes_open_control_channels(tmp_path: Path) -> None:
    async with await FakeEngine.start(tmp_path) as engine:
        client = client_for(engine)
        control = await client.connect()

        await client.close()

        assert control.closed
        await asyncio.wait_for(control.done(), timeout=1)
        await client.close()


def client_for(
    engine: FakeEngine,
    *,
    operation_timeout: float = 1,
    token: str | None = None,
    zero_rtt: bool = False,
) -> rstream.Client:
    return rstream.Client(
        engine=engine.address,
        no_token=token is None,
        operation_timeout=operation_timeout,
        read_config_file=False,
        token=token,
        tls=rstream.TLSOptions(
            ca_file=str(engine.ca_file),
            server_name="localhost",
        ),
        zero_rtt=zero_rtt,
    )


class FakeEngine:
    def __init__(
        self,
        server: asyncio.AbstractServer,
        address: str,
        ca_file: Path,
    ) -> None:
        self.server = server
        self.address = address
        self.ca_file = ca_file
        self.next_control_hang = False
        self.next_open_tunnel_hang = False
        self.next_close_tunnel_hang = False
        self.next_close_control_hang = False
        self.next_stream_empty_response = False
        self.next_stream_hang = False
        self.next_proxy_hang = False
        self.close_tunnel_requests = 0
        self.open_tunnel_requests = 0
        self.stream_requests: list[tuple[str, bool]] = []
        self.proxy_requests: list[tuple[str, bool]] = []
        self.proxy_tokens: list[str | None] = []
        self._control_writer: asyncio.StreamWriter | None = None
        self._pending_proxy_responses: asyncio.Queue[pb.Message] = asyncio.Queue()
        self._proxy_streams: asyncio.Queue[rstream.RstreamStream] = asyncio.Queue()
        self._tunnel_sequence = 0
        self._writers: set[asyncio.StreamWriter] = set()
        self._hold_tasks: set[asyncio.Task[None]] = set()
        self._closed_event = asyncio.Event()

    @classmethod
    async def start(
        cls,
        tmp_path: Path,
        *,
        name: str = "engine",
        ca: trustme.CA | None = None,
    ) -> FakeEngine:
        certificate_authority = ca or trustme.CA()
        cert = certificate_authority.issue_cert("localhost", "127.0.0.1")
        ca_file = tmp_path / f"{name}-ca.pem"
        cert_file = tmp_path / f"{name}-cert.pem"
        key_file = tmp_path / f"{name}-key.pem"
        certificate_authority.cert_pem.write_to_path(ca_file)
        cert.cert_chain_pems[0].write_to_path(cert_file)
        cert.private_key_pem.write_to_path(key_file)
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)
        ssl_context.set_alpn_protocols(["rstrm/1"])
        engine = cls.__new__(cls)
        server = await asyncio.start_server(
            engine._handle_connection,
            "127.0.0.1",
            0,
            ssl=ssl_context,
        )
        socket = server.sockets[0]
        host, port = socket.getsockname()[:2]
        cls.__init__(engine, server, f"{host}:{port}", ca_file)
        return engine

    async def __aenter__(self) -> FakeEngine:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        self._closed_event.set()
        for writer in tuple(self._writers):
            writer.close()
        await asyncio.gather(
            *(writer.wait_closed() for writer in tuple(self._writers)),
            return_exceptions=True,
        )
        for task in tuple(self._hold_tasks):
            task.cancel()
        await asyncio.gather(*self._hold_tasks, return_exceptions=True)
        self.server.close()
        await self.server.wait_closed()

    async def request_proxy_connection(
        self,
        tunnel_id: str,
        stream_id: str,
        *,
        proxy_endpoint: str | None = None,
        include_secret: bool = True,
        secret: str = "stream-secret",
    ) -> pb.Message:
        writer = self._control_writer
        assert writer is not None
        message = pb.Message()
        message.proxy_conn_req.tunnel_id = tunnel_id
        message.proxy_conn_req.stream_id = stream_id
        if proxy_endpoint is not None:
            message.proxy_conn_req.proxy_endpoint.CopyFrom(
                StringValue(value=proxy_endpoint)
            )
        if include_secret:
            message.proxy_conn_req.secret.CopyFrom(StringValue(value=secret))
        await write_message(writer, message)
        return await asyncio.wait_for(self._pending_proxy_responses.get(), timeout=1)

    async def next_proxy_stream(self) -> rstream.RstreamStream:
        return await asyncio.wait_for(self._proxy_streams.get(), timeout=1)

    async def close_control_transport(self) -> None:
        writer = self._control_writer
        assert writer is not None
        writer.close()
        await writer.wait_closed()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._writers.add(writer)
        try:
            message = await read_message(reader)
            payload = message.WhichOneof("payload")
            if payload == "open_control_channel_req":
                await self._handle_control_channel(reader, writer)
                return
            if payload == "stream_req":
                await self._handle_stream(message.stream_req, reader, writer)
                return
            if payload == "proxy_req":
                await self._handle_proxy(message.proxy_req, reader, writer)
                return
        finally:
            self._writers.discard(writer)
            writer.close()
            await writer.wait_closed()

    async def _handle_control_channel(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        if self._consume("next_control_hang"):
            await self._hold()
        self._control_writer = writer
        response = pb.Message()
        response.open_control_channel_rsp.ok.client_id = "cli_test"
        response.open_control_channel_rsp.ok.server_details.agent.CopyFrom(
            StringValue(value="fake-engine")
        )
        await write_message(writer, response)
        while True:
            message = await read_message(reader)
            payload = message.WhichOneof("payload")
            if payload == "open_tunnel_req":
                await self._handle_open_tunnel(message.open_tunnel_req, writer)
                continue
            if payload == "close_tunnel_req":
                await self._handle_close_tunnel(message.close_tunnel_req, writer)
                continue
            if payload == "close_control_channel_req":
                await self._handle_close_control_channel(writer)
                return
            if payload == "proxy_conn_rsp":
                await self._pending_proxy_responses.put(message)
                continue
            if payload == "heartbeat":
                continue

    async def _handle_open_tunnel(
        self,
        request: pb.OpenTunnelReq,
        writer: asyncio.StreamWriter,
    ) -> None:
        self.open_tunnel_requests += 1
        if self._consume("next_open_tunnel_hang"):
            return
        self._tunnel_sequence += 1
        response = pb.Message()
        response.open_tunnel_rsp.request_id = request.request_id
        response.open_tunnel_rsp.tunnel_properties.id.CopyFrom(
            StringValue(value=f"tun_test_{self._tunnel_sequence}")
        )
        response.open_tunnel_rsp.tunnel_properties.type.CopyFrom(
            StringValue(value="bytestream")
        )
        if request.tunnel_properties.HasField("protocol"):
            response.open_tunnel_rsp.tunnel_properties.protocol.CopyFrom(
                request.tunnel_properties.protocol
            )
        else:
            response.open_tunnel_rsp.tunnel_properties.protocol.CopyFrom(
                StringValue(value="http")
            )
        response.open_tunnel_rsp.tunnel_properties.hostname.CopyFrom(
            StringValue(value="test.localhost")
        )
        if request.tunnel_properties.HasField("port"):
            response.open_tunnel_rsp.tunnel_properties.port.CopyFrom(
                request.tunnel_properties.port
            )
        if request.tunnel_properties.HasField("allow_cross_region_routing"):
            response.open_tunnel_rsp.tunnel_properties.allow_cross_region_routing.CopyFrom(
                request.tunnel_properties.allow_cross_region_routing
            )
        await write_message(writer, response)

    async def _handle_close_tunnel(
        self,
        request: pb.CloseTunnelReq,
        writer: asyncio.StreamWriter,
    ) -> None:
        self.close_tunnel_requests += 1
        if self._consume("next_close_tunnel_hang"):
            return
        response = pb.Message()
        response.close_tunnel_rsp.tunnel_id = request.tunnel_id
        await write_message(writer, response)

    async def _handle_close_control_channel(
        self,
        writer: asyncio.StreamWriter,
    ) -> None:
        if self._consume("next_close_control_hang"):
            await self._hold()
        response = pb.Message()
        response.close_control_channel_rsp.CopyFrom(pb.CloseControlChannelRsp())
        await write_message(writer, response)

    async def _handle_stream(
        self,
        request: pb.StreamReq,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        zero_rtt = request.HasField("zero_rtt") and request.zero_rtt.value
        self.stream_requests.append((request.tunnel_id_name, zero_rtt))
        if self._consume("next_stream_hang"):
            await self._hold()
        if not zero_rtt:
            response = pb.Message()
            if self._consume("next_stream_empty_response"):
                response.stream_rsp.CopyFrom(pb.StreamRsp())
            else:
                response.stream_rsp.stream_id = "stream_test"
            await write_message(writer, response)
        request_payload = await reader.readexactly(4)
        assert request_payload == b"ping"
        writer.write(b"PONG")
        await writer.drain()

    async def _handle_proxy(
        self,
        request: pb.ProxyReq,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        zero_rtt = request.HasField("zero_rtt") and request.zero_rtt.value
        self.proxy_requests.append((request.stream_id, zero_rtt))
        self.proxy_tokens.append(
            request.client_details.token.value
            if request.client_details.HasField("token")
            else None
        )
        if self._consume("next_proxy_hang"):
            await self._hold()
        if not zero_rtt:
            response = pb.Message()
            response.proxy_rsp.CopyFrom(pb.ProxyRsp())
            await write_message(writer, response)
        await self._proxy_streams.put(rstream.RstreamStream(reader, writer))
        task = asyncio.create_task(self._hold())
        self._hold_tasks.add(task)
        task.add_done_callback(self._hold_tasks.discard)
        await task

    def _consume(self, flag: str) -> bool:
        enabled = bool(getattr(self, flag))
        setattr(self, flag, False)
        return enabled

    async def _hold(self) -> None:
        await self._closed_event.wait()
