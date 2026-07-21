"""Public runtime client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Mapping
from contextlib import suppress
from typing import TypeVar

from rstream._proto import rstream_pb2 as pb
from rstream.api import RstreamAPIClient, TokenCredentials, engine_from_project
from rstream.config import (
    ClientOptions,
    ResolvedClientOptions,
    TLSOptions,
    create_ssl_context,
    normalize_engine_address,
    resolve_client_options,
)
from rstream.control import ControlChannel
from rstream.engine_api import (
    ClientFilters,
    Event,
    EventStream,
    TunnelFilters,
    TunnelInventory,
    WatchTransport,
    list_inventory,
    tunnel_inventory_from_json,
    watch_events,
    watch_params_json,
)
from rstream.errors import ConfigurationError, ProtocolError, RuntimeError
from rstream.protocol import (
    engine_error_from_pb,
    message_with_open_control_channel_req,
    message_with_proxy_req,
    message_with_stream_req,
    read_message,
    server_details_from_pb,
    write_message,
)
from rstream.stable_domains import generate_stable_domain
from rstream.stream import RstreamStream

_T = TypeVar("_T")


class Client:
    """rstream runtime client.

    The client is async-first. Create it directly or use :meth:`from_env`,
    then open a control channel or dial a private bytestream tunnel.
    """

    def __init__(
        self,
        *,
        api_url: str | None = None,
        config_path: str | None = None,
        context: str | None = None,
        control_plane_headers: Mapping[str, str] | None = None,
        engine: str | None = None,
        connect_timeout: float = 15.0,
        heartbeat: bool = True,
        heartbeat_interval: float = 5.0,
        operation_timeout: float = 30.0,
        no_token: bool | None = None,
        project_endpoint: str | None = None,
        read_config_file: bool = True,
        region: str | None = None,
        require_token: bool = False,
        token: str | None = None,
        tls: TLSOptions | None = None,
        zero_rtt: bool = True,
    ) -> None:
        self._options = ClientOptions(
            api_url=api_url,
            config_path=config_path,
            context=context,
            control_plane_headers=control_plane_headers,
            engine=engine,
            connect_timeout=connect_timeout,
            heartbeat=heartbeat,
            heartbeat_interval=heartbeat_interval,
            operation_timeout=operation_timeout,
            no_token=no_token,
            project_endpoint=project_endpoint,
            read_config_file=read_config_file,
            region=region,
            require_token=require_token,
            token=token,
            tls=tls,
            zero_rtt=zero_rtt,
        )
        self._resolved: ResolvedClientOptions | None = None
        self._controls: set[ControlChannel] = set()
        self._control_watchers: set[asyncio.Task[None]] = set()
        self._closed = False

    @classmethod
    def from_env(
        cls,
        *,
        api_url: str | None = None,
        config_path: str | None = None,
        context: str | None = None,
        control_plane_headers: Mapping[str, str] | None = None,
        engine: str | None = None,
        connect_timeout: float = 15.0,
        heartbeat: bool = True,
        heartbeat_interval: float = 5.0,
        operation_timeout: float = 30.0,
        no_token: bool | None = None,
        project_endpoint: str | None = None,
        read_config_file: bool = True,
        region: str | None = None,
        require_token: bool = False,
        token: str | None = None,
        tls: TLSOptions | None = None,
        zero_rtt: bool = True,
    ) -> Client:
        return cls(
            api_url=api_url,
            config_path=config_path,
            context=context,
            control_plane_headers=control_plane_headers,
            engine=engine,
            connect_timeout=connect_timeout,
            heartbeat=heartbeat,
            heartbeat_interval=heartbeat_interval,
            operation_timeout=operation_timeout,
            no_token=no_token,
            project_endpoint=project_endpoint,
            read_config_file=read_config_file,
            region=region,
            require_token=require_token,
            token=token,
            tls=tls,
            zero_rtt=zero_rtt,
        )

    async def connect(self) -> ControlChannel:
        self._ensure_open()
        resolved = await self._get_resolved()
        engine = await self._resolve_engine(resolved)
        token = await self._resolve_token(resolved, engine)
        reader, writer = await self._dial_engine(engine, resolved)
        try:
            await write_message(writer, message_with_open_control_channel_req(token))
            response = await _wait_for_operation(
                read_message(reader),
                resolved.operation_timeout,
                "Timed out waiting for the engine control channel response.",
            )
            if response.WhichOneof("payload") != "open_control_channel_rsp":
                raise ProtocolError(
                    "Engine did not return OpenControlChannelRsp.",
                    code="ERR_RSTREAM_PROTOCOL",
                )
            payload = response.open_control_channel_rsp
            response_payload = payload.WhichOneof("payload")
            if response_payload == "error":
                raise engine_error_from_pb(payload.error)
            if response_payload != "ok":
                raise ProtocolError(
                    "Engine returned an empty OpenControlChannelRsp.",
                    code="ERR_RSTREAM_PROTOCOL",
                )
            control = ControlChannel(
                reader,
                writer,
                heartbeat=resolved.heartbeat,
                heartbeat_interval=resolved.heartbeat_interval,
                operation_timeout=resolved.operation_timeout,
                open_proxy_connection=lambda request: self._open_proxy_connection(
                    engine,
                    resolved,
                    request,
                ),
                server_details=server_details_from_pb(payload.ok.server_details),
            )
            self._controls.add(control)
            watcher = asyncio.create_task(self._discard_control_when_done(control))
            self._control_watchers.add(watcher)
            watcher.add_done_callback(self._control_watchers.discard)
            return control
        except BaseException:
            writer.close()
            await writer.wait_closed()
            raise

    async def dial(
        self,
        tunnel: str,
        *,
        token: str | None = None,
        zero_rtt: bool | None = None,
    ) -> RstreamStream:
        self._ensure_open()
        normalized = tunnel.strip()
        if not normalized:
            raise RuntimeError(
                "Tunnel ID or name is required.",
                code="ERR_RSTREAM_INVALID_TUNNEL",
            )
        resolved = await self._get_resolved()
        engine = await self._resolve_engine(resolved)
        auth_token = (
            token if token is not None else await self._resolve_token(resolved, engine)
        )
        use_zero_rtt = resolved.zero_rtt if zero_rtt is None else zero_rtt
        reader, writer = await self._dial_engine(engine, resolved)
        try:
            await write_message(
                writer,
                message_with_stream_req(normalized, auth_token, use_zero_rtt),
            )
            if not use_zero_rtt:
                response = await _wait_for_operation(
                    read_message(reader),
                    resolved.operation_timeout,
                    "Timed out waiting for the private stream response.",
                )
                if response.WhichOneof("payload") != "stream_rsp":
                    raise ProtocolError(
                        "Engine did not return StreamRsp.",
                        code="ERR_RSTREAM_PROTOCOL",
                    )
                stream_rsp = response.stream_rsp
                stream_payload = stream_rsp.WhichOneof("payload")
                if stream_payload == "error":
                    raise engine_error_from_pb(stream_rsp.error)
                if stream_payload != "stream_id":
                    raise ProtocolError(
                        "Engine returned an empty StreamRsp.",
                        code="ERR_RSTREAM_PROTOCOL",
                    )
            return RstreamStream(reader, writer)
        except BaseException:
            writer.close()
            await writer.wait_closed()
            raise

    async def dial_bytestream(
        self,
        tunnel: str,
        *,
        token: str | None = None,
        zero_rtt: bool | None = None,
    ) -> RstreamStream:
        return await self.dial(tunnel, token=token, zero_rtt=zero_rtt)

    async def generate_stable_hostname(self) -> str | None:
        """Derive a stable, project-scoped hostname from the resolved engine.

        Generate it once and reuse it on every ``create_tunnel`` so a
        published tunnel keeps the same address across reconnects. Returns
        ``None`` when the engine is not a managed project host, in which case
        the engine allocates an address. See :mod:`rstream.stable_domains`.
        """
        self._ensure_open()
        resolved = await self._get_resolved()
        engine = await self._resolve_engine(resolved)
        return generate_stable_domain(engine)

    async def list_tunnels(
        self,
        *,
        filters: TunnelFilters | None = None,
        limit: int | None = None,
    ) -> list[TunnelInventory]:
        """List live tunnels from the engine inventory."""
        self._ensure_open()
        engine, token, tls = await self._engine_api_target()
        params: dict[str, object] = {}
        if limit is not None:
            params["limit"] = limit
        if filters is not None:
            params["filters"] = filters.to_json()
        items = await list_inventory(
            engine=engine,
            token=token,
            path="/tunnels",
            params_json=params or None,
            tls=tls,
        )
        return [tunnel_inventory_from_json(item) for item in items]

    async def list_clients(
        self,
        *,
        filters: ClientFilters | None = None,
        limit: int | None = None,
    ) -> list[Mapping[str, object]]:
        """List live runtime clients from the engine inventory."""
        self._ensure_open()
        engine, token, tls = await self._engine_api_target()
        params: dict[str, object] = {}
        if limit is not None:
            params["limit"] = limit
        if filters is not None:
            params["filters"] = filters.to_json()
        return await list_inventory(
            engine=engine,
            token=token,
            path="/clients",
            params_json=params or None,
            tls=tls,
        )

    def watch(
        self,
        *,
        tunnels: TunnelFilters | None = None,
        clients: ClientFilters | None = None,
        transport: WatchTransport = "sse",
    ) -> EventStream:
        """Stream real-time engine events.

        Events describe tunnel and client lifecycle changes
        (``tunnel.created``, ``tunnel.updated``, ``tunnel.deleted``, and the
        client equivalents), optionally filtered. The returned stream is an
        async iterator and an async context manager; the connection closes
        when the stream is closed or the surrounding task is cancelled.
        """
        self._ensure_open()

        async def generate() -> AsyncIterator[Event]:
            engine, token, tls = await self._engine_api_target()
            source = watch_events(
                engine=engine,
                token=token,
                params_json=watch_params_json(tunnels, clients),
                tls=tls,
                transport=transport,
            )
            try:
                async for event in source:
                    yield event
            finally:
                await source.aclose()

        return EventStream(generate())

    async def _engine_api_target(self) -> tuple[str, str | None, TLSOptions | None]:
        resolved = await self._get_resolved()
        engine = await self._resolve_engine(resolved)
        token = await self._resolve_token(resolved, engine)
        return engine, token, resolved.tls

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        failure: BaseException | None = None
        for control in tuple(self._controls):
            try:
                await control.close()
            except Exception as error:
                if failure is None:
                    failure = error
        self._controls.clear()
        watchers = tuple(self._control_watchers)
        for watcher in watchers:
            watcher.cancel()
        await asyncio.gather(*watchers, return_exceptions=True)
        self._control_watchers.clear()
        self._resolved = None
        if failure is not None:
            raise failure

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        await self.close()

    async def _open_proxy_connection(
        self,
        engine: str,
        resolved: ResolvedClientOptions,
        request: pb.ProxyConnReq,
    ) -> RstreamStream:
        token = request.secret.value if request.HasField("secret") else None
        proxy_engine = engine
        if request.HasField("proxy_endpoint"):
            if token is None or not token.strip():
                raise ProtocolError(
                    "Engine did not provide credentials for the redirected stream.",
                    code="ERR_RSTREAM_PROTOCOL",
                )
            proxy_engine = request.proxy_endpoint.value.strip()
            if not proxy_engine:
                raise ProtocolError(
                    "Engine returned an empty proxy endpoint.",
                    code="ERR_RSTREAM_PROTOCOL",
                )
        reader, writer = await self._dial_engine(
            proxy_engine,
            resolved,
            use_explicit_server_name=proxy_engine == engine,
        )
        try:
            await write_message(
                writer,
                message_with_proxy_req(request.stream_id, token, resolved.zero_rtt),
            )
            if not resolved.zero_rtt:
                response = await _wait_for_operation(
                    read_message(reader),
                    resolved.operation_timeout,
                    "Timed out waiting for the proxy stream response.",
                )
                if response.WhichOneof("payload") != "proxy_rsp":
                    raise ProtocolError(
                        "Engine did not return ProxyRsp.",
                        code="ERR_RSTREAM_PROTOCOL",
                    )
                proxy_rsp = response.proxy_rsp
                if proxy_rsp.HasField("error"):
                    raise engine_error_from_pb(proxy_rsp.error)
            return RstreamStream(reader, writer)
        except BaseException:
            writer.close()
            await writer.wait_closed()
            raise

    async def _dial_engine(
        self,
        engine: str,
        resolved: ResolvedClientOptions,
        *,
        use_explicit_server_name: bool = True,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        ssl_context, server_hostname = create_ssl_context(
            engine,
            resolved.tls,
            use_explicit_server_name=use_explicit_server_name,
        )
        host, port = _split_engine(engine)
        return await _wait_for_operation(
            asyncio.open_connection(
                host,
                port,
                ssl=ssl_context,
                server_hostname=server_hostname,
            ),
            resolved.connect_timeout,
            "Timed out connecting to the rstream engine.",
        )

    async def _resolve_engine(self, resolved: ResolvedClientOptions) -> str:
        if resolved.region is None and resolved.engine is not None:
            return resolved.engine
        if resolved.project_endpoint is None:
            raise ConfigurationError(
                "Engine is required but not configured.",
                code="ERR_RSTREAM_ENGINE_REQUIRED",
            )
        credentials = (
            TokenCredentials(resolved.token) if resolved.token is not None else None
        )
        project = await RstreamAPIClient(
            api_url=resolved.api_url,
            control_plane_headers=resolved.control_plane_headers,
            credentials=credentials,
        ).resolve_tunnels_project(resolved.project_endpoint)
        return engine_from_project(project, resolved.region)

    async def _resolve_token(
        self,
        resolved: ResolvedClientOptions,
        engine: str,
    ) -> str | None:
        if resolved.no_token:
            return None
        token = resolved.token
        if token is None:
            return None
        normalized_engine = normalize_engine_address(engine)
        if normalized_engine is None:
            return token
        return token

    async def _get_resolved(self) -> ResolvedClientOptions:
        if self._resolved is None:
            self._resolved = await resolve_client_options(self._options)
        return self._resolved

    async def _discard_control_when_done(self, control: ControlChannel) -> None:
        with suppress(BaseException):
            await control.done()
        self._controls.discard(control)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError(
                "rstream client is closed.",
                code="ERR_RSTREAM_CLIENT_CLOSED",
            )

    def with_options(
        self,
        *,
        api_url: str | None = None,
        config_path: str | None = None,
        context: str | None = None,
        control_plane_headers: Mapping[str, str] | None = None,
        engine: str | None = None,
        connect_timeout: float | None = None,
        heartbeat: bool | None = None,
        heartbeat_interval: float | None = None,
        operation_timeout: float | None = None,
        no_token: bool | None = None,
        project_endpoint: str | None = None,
        read_config_file: bool | None = None,
        region: str | None = None,
        require_token: bool | None = None,
        token: str | None = None,
        tls: TLSOptions | None = None,
        zero_rtt: bool | None = None,
    ) -> Client:
        options = self._options
        return Client(
            api_url=api_url if api_url is not None else options.api_url,
            config_path=config_path if config_path is not None else options.config_path,
            context=context if context is not None else options.context,
            control_plane_headers=(
                control_plane_headers
                if control_plane_headers is not None
                else options.control_plane_headers
            ),
            engine=engine if engine is not None else options.engine,
            connect_timeout=(
                connect_timeout
                if connect_timeout is not None
                else options.connect_timeout
            ),
            heartbeat=heartbeat if heartbeat is not None else options.heartbeat,
            heartbeat_interval=(
                heartbeat_interval
                if heartbeat_interval is not None
                else options.heartbeat_interval
            ),
            operation_timeout=(
                operation_timeout
                if operation_timeout is not None
                else options.operation_timeout
            ),
            no_token=no_token if no_token is not None else options.no_token,
            project_endpoint=(
                project_endpoint
                if project_endpoint is not None
                else options.project_endpoint
            ),
            read_config_file=(
                read_config_file
                if read_config_file is not None
                else options.read_config_file
            ),
            region=region if region is not None else options.region,
            require_token=(
                require_token if require_token is not None else options.require_token
            ),
            token=token if token is not None else options.token,
            tls=tls if tls is not None else options.tls,
            zero_rtt=zero_rtt if zero_rtt is not None else options.zero_rtt,
        )


def _split_engine(engine: str) -> tuple[str, int]:
    if ":" not in engine:
        return engine, 443
    host, port_text = engine.rsplit(":", 1)
    try:
        port = int(port_text)
    except ValueError as error:
        raise ConfigurationError(
            "Engine port must be an integer between 1 and 65535.",
            code="ERR_RSTREAM_INVALID_ENGINE",
        ) from error
    if not 1 <= port <= 65_535:
        raise ConfigurationError(
            "Engine port must be an integer between 1 and 65535.",
            code="ERR_RSTREAM_INVALID_ENGINE",
        )
    return host, port


async def _wait_for_operation(
    awaitable: Awaitable[_T],
    timeout: float,
    message: str,
) -> _T:
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError as error:
        raise RuntimeError(message, code="ERR_RSTREAM_OPERATION_TIMEOUT") from error
