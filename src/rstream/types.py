"""Public types used by the rstream runtime SDK."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

TunnelType = Literal["bytestream", "datagram"]
TunnelProtocol = Literal["tls", "tcp", "dtls", "quic", "http"]
HTTPVersion = Literal["http/1.1", "h2", "h2c", "h3"]
TLSMode = Literal["passthrough", "terminated"]


@dataclass(frozen=True)
class TunnelAuth:
    """Authentication options applied to a tunnel endpoint."""

    token: bool | None = None
    rstream: bool | None = None
    challenge: bool | None = None


@dataclass(frozen=True)
class TunnelProperties:
    """Tunnel properties accepted by the engine."""

    id: str | None = None
    creation_date: datetime | None = None
    name: str | None = None
    type: TunnelType | None = None
    publish: bool | None = None
    protocol: TunnelProtocol | None = None
    labels: Mapping[str, str] = field(default_factory=dict)
    geo_ip: tuple[str, ...] = ()
    trusted_ips: tuple[str, ...] = ()
    host: str | None = None
    tls_mode: TLSMode | None = None
    tls_alpns: tuple[str, ...] = ()
    tls_min_version: str | None = None
    tls_ciphers: tuple[str, ...] = ()
    mtls_auth: bool | None = None
    http_version: HTTPVersion | None = None
    http_use_tls: bool | None = None
    token_auth: bool | None = None
    rstream_auth: bool | None = None
    challenge_mode: bool | None = None
    hostname: str | None = None
    port: int | None = None
    upstream_tls: bool | None = None
    datagram_guaranteed_delivery: bool | None = None
    allow_cross_region_routing: bool | None = None


@dataclass(frozen=True)
class CreateTunnelOptions:
    """Options accepted by :meth:`ControlChannel.create_tunnel`."""

    name: str | None = None
    type: TunnelType | None = None
    publish: bool | None = None
    protocol: TunnelProtocol | None = None
    labels: Mapping[str, str] = field(default_factory=dict)
    geo_ip: tuple[str, ...] = ()
    trusted_ips: tuple[str, ...] = ()
    tls_mode: TLSMode | None = None
    tls_alpns: tuple[str, ...] = ()
    tls_min_version: str | None = None
    tls_ciphers: tuple[str, ...] = ()
    mtls_auth: bool | None = None
    http_version: HTTPVersion | None = None
    token_auth: bool | None = None
    rstream_auth: bool | None = None
    challenge_mode: bool | None = None
    hostname: str | None = None
    port: int | None = None
    upstream_tls: bool | None = None
    allow_cross_region_routing: bool | None = None
    auth: TunnelAuth | None = None


@dataclass(frozen=True)
class ServerDetails:
    """Metadata returned by the engine when a control channel opens."""

    agent: str | None = None
    channel: str | None = None
    version: str | None = None
    plan: str | None = None
    provider: str | None = None
    region: str | None = None
    update: str | None = None
