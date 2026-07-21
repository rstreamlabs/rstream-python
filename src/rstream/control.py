"""Control channel implementation."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from typing import TypeVar

from rstream._proto import rstream_pb2 as pb
from rstream.errors import ProtocolError, RuntimeError, UnsupportedFeatureError
from rstream.protocol import (
    engine_error_from_pb,
    error_to_pb,
    message_with_close_control_channel_req,
    message_with_close_tunnel_req,
    message_with_heartbeat,
    message_with_open_tunnel_req,
    message_with_proxy_conn_rsp,
    read_message,
    tunnel_properties_from_pb,
    write_message,
)
from rstream.stream import RstreamStream
from rstream.tunnel import BytestreamTunnel
from rstream.types import (
    CreateTunnelOptions,
    HTTPVersion,
    ServerDetails,
    TLSMode,
    TunnelAuth,
    TunnelProperties,
    TunnelProtocol,
    TunnelType,
)

OpenProxyConnection = Callable[[pb.ProxyConnReq], Awaitable[RstreamStream]]
_T = TypeVar("_T")


class ControlChannel:
    """Open control channel used to create and manage tunnels."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        heartbeat: bool,
        heartbeat_interval: float,
        operation_timeout: float,
        open_proxy_connection: OpenProxyConnection,
        server_details: ServerDetails | None = None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._heartbeat = heartbeat
        self._heartbeat_interval = heartbeat_interval
        self._operation_timeout = operation_timeout
        self._open_proxy_connection = open_proxy_connection
        self._server_details = server_details
        self._pending_tunnels: dict[str, asyncio.Future[BytestreamTunnel]] = {}
        self._pending_closes: dict[str, asyncio.Future[None]] = {}
        self._tunnels: dict[str, BytestreamTunnel] = {}
        self._write_lock = asyncio.Lock()
        self._closed = False
        self._closing = False
        self._close_error: BaseException | None = None
        loop = asyncio.get_running_loop()
        self._done = loop.create_future()
        self._read_task = asyncio.create_task(self._read_loop())
        self._heartbeat_task: asyncio.Task[None] | None = None
        if heartbeat and heartbeat_interval > 0:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def server_details(self) -> ServerDetails | None:
        return self._server_details

    async def done(self) -> None:
        await self._done

    async def create_tunnel(
        self,
        options: CreateTunnelOptions | None = None,
        *,
        name: str | None = None,
        type: TunnelType | None = None,
        publish: bool | None = None,
        protocol: TunnelProtocol | None = None,
        labels: Mapping[str, str] | None = None,
        geo_ip: tuple[str, ...] = (),
        trusted_ips: tuple[str, ...] = (),
        tls_mode: TLSMode | None = None,
        tls_alpns: tuple[str, ...] = (),
        tls_min_version: str | None = None,
        tls_ciphers: tuple[str, ...] = (),
        mtls_auth: bool | None = None,
        http_version: HTTPVersion | None = None,
        token_auth: bool | None = None,
        rstream_auth: bool | None = None,
        challenge_mode: bool | None = None,
        hostname: str | None = None,
        port: int | None = None,
        upstream_tls: bool | None = None,
        allow_cross_region_routing: bool | None = None,
        auth: TunnelAuth | None = None,
    ) -> BytestreamTunnel:
        explicit_options = CreateTunnelOptions(
            name=name,
            type=type,
            publish=publish,
            protocol=protocol,
            labels={} if labels is None else labels,
            geo_ip=geo_ip,
            trusted_ips=trusted_ips,
            tls_mode=tls_mode,
            tls_alpns=tls_alpns,
            tls_min_version=tls_min_version,
            tls_ciphers=tls_ciphers,
            mtls_auth=mtls_auth,
            http_version=http_version,
            token_auth=token_auth,
            rstream_auth=rstream_auth,
            challenge_mode=challenge_mode,
            hostname=hostname,
            port=port,
            upstream_tls=upstream_tls,
            allow_cross_region_routing=allow_cross_region_routing,
            auth=auth,
        )
        if options is not None and explicit_options != CreateTunnelOptions():
            raise RuntimeError(
                "Use either a CreateTunnelOptions object or keyword options.",
                code="ERR_RSTREAM_INVALID_TUNNEL",
            )
        tunnel_options = options or explicit_options
        if tunnel_options.type is not None and tunnel_options.type != "bytestream":
            raise UnsupportedFeatureError(
                "Only bytestream tunnels are supported by rstream-python.",
                code="ERR_RSTREAM_UNSUPPORTED_TUNNEL",
            )
        if tunnel_options.http_version == "h3":
            raise UnsupportedFeatureError(
                "HTTP/3 tunnels require datagram support, which rstream-python "
                "does not support.",
                code="ERR_RSTREAM_UNSUPPORTED_TUNNEL",
            )
        if self._closed or self._closing:
            raise RuntimeError(
                "Control channel is closed.",
                code="ERR_RSTREAM_CONTROL_CLOSED",
            )
        properties = _normalize_bytestream_options(tunnel_options)
        request_id = str(uuid.uuid4())
        future: asyncio.Future[BytestreamTunnel] = (
            asyncio.get_running_loop().create_future()
        )
        self._pending_tunnels[request_id] = future
        try:
            await self._write(message_with_open_tunnel_req(request_id, properties))
            return await self._await_pending(
                future,
                "Timed out waiting for the engine tunnel creation response.",
            )
        except BaseException:
            self._pending_tunnels.pop(request_id, None)
            raise

    async def close_tunnel(self, tunnel_id: str) -> None:
        tunnel = self._tunnels.get(tunnel_id)
        if tunnel is None or tunnel.closed:
            return
        future = self._pending_closes.get(tunnel_id)
        owner = future is None
        if future is None:
            future = asyncio.get_running_loop().create_future()
            self._pending_closes[tunnel_id] = future
        if owner:
            try:
                await self._write(message_with_close_tunnel_req(tunnel_id))
            except BaseException:
                self._pending_closes.pop(tunnel_id, None)
                raise
        try:
            await self._await_pending(
                future,
                "Timed out waiting for the engine tunnel close response.",
            )
        except BaseException:
            if self._pending_closes.get(tunnel_id) is future:
                self._pending_closes.pop(tunnel_id, None)
            raise

    async def close(self) -> None:
        if self._closed:
            return
        if not self._closing:
            self._closing = True
            with suppress(Exception):
                await self._write(message_with_close_control_channel_req())
        try:
            await asyncio.wait_for(
                asyncio.shield(self._done),
                timeout=self._operation_timeout,
            )
        except asyncio.TimeoutError as error:
            timeout = RuntimeError(
                "Timed out waiting for the engine control-channel close response.",
                code="ERR_RSTREAM_OPERATION_TIMEOUT",
            )
            self._fail(timeout)
            raise timeout from error

    async def __aenter__(self) -> ControlChannel:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        await self.close()

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(self._heartbeat_interval)
                if not self._closed:
                    await self._write(message_with_heartbeat())
        except BaseException as error:
            if not self._closed:
                self._fail(error)

    async def _read_loop(self) -> None:
        try:
            while not self._closed:
                await self._handle_message(await read_message(self._reader))
        except BaseException as error:
            if not self._closed:
                self._fail(error)

    async def _handle_message(self, message: pb.Message) -> None:
        payload = message.WhichOneof("payload")
        if payload == "open_tunnel_rsp":
            self._handle_open_tunnel_rsp(message.open_tunnel_rsp)
            return
        if payload == "close_tunnel_rsp":
            self._handle_close_tunnel_rsp(message.close_tunnel_rsp.tunnel_id)
            return
        if payload == "proxy_conn_req":
            await self._handle_proxy_conn_req(message.proxy_conn_req)
            return
        if payload == "close_control_channel_rsp":
            self._finish()
            return

    def _handle_open_tunnel_rsp(self, response: pb.OpenTunnelRsp) -> None:
        pending = self._pending_tunnels.pop(response.request_id, None)
        if pending is None:
            return
        payload = response.WhichOneof("payload")
        if payload == "error":
            pending.set_exception(engine_error_from_pb(response.error))
            return
        if payload != "tunnel_properties":
            pending.set_exception(
                ProtocolError(
                    "Engine returned an empty OpenTunnelRsp.",
                    code="ERR_RSTREAM_PROTOCOL",
                )
            )
            return
        properties = tunnel_properties_from_pb(response.tunnel_properties)
        tunnel = BytestreamTunnel(self, properties)
        self._tunnels[tunnel.id] = tunnel
        pending.set_result(tunnel)

    def _handle_close_tunnel_rsp(self, tunnel_id: str) -> None:
        tunnel = self._tunnels.pop(tunnel_id, None)
        if tunnel is not None:
            tunnel.on_close()
        pending = self._pending_closes.pop(tunnel_id, None)
        if pending is not None and not pending.done():
            pending.set_result(None)

    async def _handle_proxy_conn_req(self, request: pb.ProxyConnReq) -> None:
        tunnel = self._tunnels.get(request.tunnel_id)
        if tunnel is None:
            await self._write(
                message_with_proxy_conn_rsp(
                    request.stream_id,
                    error_to_pb("Tunnel is not open on this client."),
                )
            )
            return
        try:
            stream = await self._open_proxy_connection(request)
            if not tunnel.deliver(stream):
                await self._write(
                    message_with_proxy_conn_rsp(
                        request.stream_id,
                        error_to_pb("Tunnel is closed."),
                    )
                )
                return
            await self._write(message_with_proxy_conn_rsp(request.stream_id))
        except BaseException as error:
            await self._write(
                message_with_proxy_conn_rsp(request.stream_id, error_to_pb(str(error)))
            )

    async def _write(self, message: pb.Message) -> None:
        async with self._write_lock:
            await write_message(self._writer, message)

    async def _await_pending(
        self,
        future: asyncio.Future[_T],
        message: str,
    ) -> _T:
        try:
            return await asyncio.wait_for(
                asyncio.shield(future),
                timeout=self._operation_timeout,
            )
        except asyncio.TimeoutError as error:
            timeout = RuntimeError(message, code="ERR_RSTREAM_OPERATION_TIMEOUT")
            raise timeout from error

    def _fail(self, error: BaseException) -> None:
        self._close_error = error
        self._finish()

    def _finish(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
        if self._read_task is not asyncio.current_task():
            self._read_task.cancel()
        self._writer.close()
        error = self._close_error or RuntimeError(
            "Control channel closed.",
            code="ERR_RSTREAM_CONTROL_CLOSED",
        )
        for tunnel_pending in self._pending_tunnels.values():
            if not tunnel_pending.done():
                tunnel_pending.set_exception(error)
        for close_pending in self._pending_closes.values():
            if not close_pending.done():
                close_pending.set_exception(error)
        for tunnel in self._tunnels.values():
            tunnel.on_close(error)
        self._pending_tunnels.clear()
        self._pending_closes.clear()
        self._tunnels.clear()
        if not self._done.done():
            if self._close_error is None:
                self._done.set_result(None)
            else:
                self._done.set_exception(self._close_error)


def _normalize_bytestream_options(options: CreateTunnelOptions) -> TunnelProperties:
    if options.allow_cross_region_routing is not None and options.protocol != "tcp":
        raise RuntimeError(
            "Cross-region routing policy requires protocol='tcp'.",
            code="ERR_RSTREAM_INVALID_TUNNEL",
        )
    if options.port is not None and options.protocol != "tcp":
        raise RuntimeError(
            "A published port requires protocol='tcp'.",
            code="ERR_RSTREAM_INVALID_TUNNEL",
        )
    if options.port is not None and not 1 <= options.port <= 65_535:
        raise RuntimeError(
            "The published TCP port must be between 1 and 65535.",
            code="ERR_RSTREAM_INVALID_TUNNEL",
        )
    if options.protocol == "tcp" and options.publish is False:
        raise RuntimeError(
            "TCP tunnels must be published.",
            code="ERR_RSTREAM_INVALID_TUNNEL",
        )
    if options.protocol == "tcp" and (
        options.hostname is not None
        or options.tls_mode is not None
        or options.tls_alpns
        or options.tls_min_version is not None
        or options.tls_ciphers
        or options.mtls_auth is not None
        or options.http_version is not None
        or options.upstream_tls is not None
        or options.token_auth is not None
        or options.rstream_auth is not None
        or options.challenge_mode is not None
        or options.auth is not None
    ):
        raise RuntimeError(
            "TCP tunnels do not accept hostname, HTTP, TLS, "
            "or edge authentication options.",
            code="ERR_RSTREAM_INVALID_TUNNEL",
        )
    auth = options.auth
    token_auth = (
        options.token_auth
        if options.token_auth is not None
        else auth.token
        if auth
        else None
    )
    rstream_auth = (
        options.rstream_auth
        if options.rstream_auth is not None
        else auth.rstream
        if auth
        else None
    )
    challenge_mode = (
        options.challenge_mode
        if options.challenge_mode is not None
        else auth.challenge
        if auth
        else None
    )
    return TunnelProperties(
        name=options.name,
        type="bytestream",
        publish=True if options.protocol == "tcp" else options.publish,
        protocol=options.protocol,
        labels=dict(options.labels),
        geo_ip=tuple(options.geo_ip),
        trusted_ips=tuple(options.trusted_ips),
        tls_mode=options.tls_mode,
        tls_alpns=tuple(options.tls_alpns),
        tls_min_version=options.tls_min_version,
        tls_ciphers=tuple(options.tls_ciphers),
        mtls_auth=options.mtls_auth,
        http_version=options.http_version,
        token_auth=token_auth,
        rstream_auth=rstream_auth,
        challenge_mode=challenge_mode,
        hostname=options.hostname,
        port=options.port,
        upstream_tls=options.upstream_tls,
        allow_cross_region_routing=options.allow_cross_region_routing,
    )
