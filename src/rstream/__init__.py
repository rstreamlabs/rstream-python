"""Python SDK for rstream tunnels."""

from importlib import import_module
from types import ModuleType

from rstream.client import Client
from rstream.config import ClientOptions, ResolvedClientOptions, TLSOptions
from rstream.control import ControlChannel
from rstream.engine_api import (
    ClientFilters,
    Event,
    EventStream,
    TunnelFilters,
    TunnelInventory,
    WatchTransport,
)
from rstream.errors import (
    ConfigurationError,
    EngineError,
    ProtocolError,
    RstreamError,
    RstreamRuntimeError,
    RuntimeError,
    UnsupportedFeatureError,
)
from rstream.stable_domains import engine_hostname, generate_stable_domain
from rstream.stream import RstreamStream
from rstream.tunnel import BytestreamTunnel, format_forwarding_address
from rstream.types import (
    CreateTunnelOptions,
    ServerDetails,
    TunnelAuth,
    TunnelProperties,
)
from rstream.version import __version__
from rstream.webhooks import (
    WebhookEvent,
    Webhooks,
    build_headers,
    generate_signing_secret,
    sign_payload,
    verify_event,
)


def __getattr__(name: str) -> ModuleType:
    if name == "asgi":
        return import_module("rstream.asgi")
    if name == "wsgi":
        return import_module("rstream.wsgi")
    raise AttributeError(f"module 'rstream' has no attribute {name!r}")


__all__ = [
    "BytestreamTunnel",
    "Client",
    "ClientFilters",
    "ClientOptions",
    "ConfigurationError",
    "ControlChannel",
    "CreateTunnelOptions",
    "EngineError",
    "Event",
    "EventStream",
    "ProtocolError",
    "ResolvedClientOptions",
    "RstreamError",
    "RstreamRuntimeError",
    "RstreamStream",
    "RuntimeError",
    "ServerDetails",
    "TLSOptions",
    "TunnelAuth",
    "TunnelFilters",
    "TunnelInventory",
    "TunnelProperties",
    "UnsupportedFeatureError",
    "WatchTransport",
    "WebhookEvent",
    "Webhooks",
    "__version__",
    "asgi",
    "build_headers",
    "engine_hostname",
    "format_forwarding_address",
    "generate_stable_domain",
    "generate_signing_secret",
    "sign_payload",
    "verify_event",
    "wsgi",
]
