"""Configuration resolution compatible with the rstream CLI config file."""

from __future__ import annotations

import base64
import json
import os
import re
import ssl
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

from rstream.errors import ConfigurationError, UnsupportedFeatureError

DEFAULT_API_URL = "https://rstream.io"


@dataclass(frozen=True)
class TLSOptions:
    """TLS settings used when connecting to the engine."""

    ca_file: str | None = None
    cert_file: str | None = None
    key_file: str | None = None
    certificate: str | None = None
    key: str | None = None
    server_name: str | None = None
    insecure_skip_verify: bool = False


@dataclass(frozen=True)
class ClientOptions:
    """Input options accepted by :class:`rstream.Client`."""

    api_url: str | None = None
    config_path: str | None = None
    context: str | None = None
    control_plane_headers: Mapping[str, str] | None = None
    engine: str | None = None
    connect_timeout: float = 15.0
    heartbeat: bool = True
    heartbeat_interval: float = 5.0
    operation_timeout: float = 30.0
    no_token: bool | None = None
    project_endpoint: str | None = None
    read_config_file: bool = True
    region: str | None = None
    require_token: bool = False
    tls: TLSOptions | None = None
    token: str | None = None
    zero_rtt: bool = True
    tunnel_transport: str | None = None


@dataclass(frozen=True)
class ResolvedClientOptions:
    """Fully resolved options used by the runtime client."""

    api_url: str
    control_plane_headers: Mapping[str, str]
    engine: str | None
    connect_timeout: float
    heartbeat: bool
    heartbeat_interval: float
    operation_timeout: float
    no_token: bool
    project_endpoint: str | None
    region: str | None
    tls: TLSOptions | None
    token: str | None
    zero_rtt: bool
    tunnel_transport: str


@dataclass(frozen=True)
class _TokenConfig:
    value: str | None = None
    kind: str | None = None
    provider: str | None = None
    service: str | None = None
    account: str | None = None


@dataclass(frozen=True)
class _MTLSConfig:
    certificate: str | None = None
    certificate_file: str | None = None
    key: str | None = None
    key_file: str | None = None
    storage: Mapping[str, object] | None = None


@dataclass(frozen=True)
class _AuthConfig:
    token: _TokenConfig | None = None
    mtls: _MTLSConfig | None = None


@dataclass(frozen=True)
class _TransportConfig:
    raw: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _EnvironmentConfig:
    api_url: str
    auth: _AuthConfig | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    transport: _TransportConfig | None = None


@dataclass(frozen=True)
class _ContextConfig:
    name: str
    api_url: str | None = None
    auth: _AuthConfig | None = None
    engine: str | None = None
    project_endpoint: str | None = None
    region: str | None = None
    transport: _TransportConfig | None = None


@dataclass(frozen=True)
class _ConfigFile:
    default_context: str | None = None
    contexts: Sequence[_ContextConfig] = ()
    environments: Sequence[_EnvironmentConfig] = ()


@dataclass(frozen=True)
class _ResolvedConfig:
    api_url: str
    control_plane_headers: Mapping[str, str] = field(default_factory=dict)
    context_engine: str | None = None
    engine: str | None = None
    project_endpoint: str | None = None
    region: str | None = None
    tls: TLSOptions | None = None
    token: str | None = None
    tunnel_transport: str | None = None


@dataclass(frozen=True)
class _EnvSettings:
    api_url: str | None = None
    config_path: str | None = None
    context: str | None = None
    control_plane_headers: Mapping[str, str] = field(default_factory=dict)
    engine: str | None = None
    mtls_cert: str | None = None
    mtls_key: str | None = None
    region: str | None = None
    token: str | None = None
    tunnel_transport: str | None = None
    use_quic: bool | None = None


_DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)
_HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_RESERVED_CONTROL_PLANE_HEADERS = {
    "authorization",
    "connection",
    "content-length",
    "cookie",
    "forwarded",
    "host",
    "keep-alive",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def default_config_path() -> str:
    return str(Path.home() / ".rstream" / "config.yaml")


async def resolve_client_options(options: ClientOptions) -> ResolvedClientOptions:
    env = _read_env()
    config = _resolve_config(options, env)
    explicit_mtls = _env_has_mtls(env) or _tls_has_client_certificate(options.tls)
    token = (
        None
        if options.no_token
        else _first_defined(
            options.token,
            env.token,
            None if explicit_mtls else config.token,
        )
    )
    tls = _merge_tls_options(config.tls, options.tls)
    if token is not None and _tls_has_client_certificate(tls):
        raise ConfigurationError(
            "Token authentication and mTLS authentication cannot be used together.",
            code="ERR_RSTREAM_AUTH_CONFLICT",
        )
    if token is not None:
        _validate_token_expiry(token)
    requested_transport = _resolve_tunnel_transport_mode(
        options.tunnel_transport,
        env.tunnel_transport,
        env.use_quic,
        config.tunnel_transport,
    )
    if requested_transport == "quic":
        raise UnsupportedFeatureError(
            "QUIC tunnel transport is not supported by rstream-python.",
            code="ERR_RSTREAM_UNSUPPORTED_TRANSPORT",
        )
    if options.require_token and token is None and not _tls_has_client_certificate(tls):
        raise ConfigurationError(
            "Authentication is required but not configured.",
            code="ERR_RSTREAM_AUTH_REQUIRED",
        )
    if options.connect_timeout <= 0:
        raise ConfigurationError(
            "connect_timeout must be positive.",
            code="ERR_RSTREAM_INVALID_TIMEOUT",
        )
    if options.operation_timeout <= 0:
        raise ConfigurationError(
            "operation_timeout must be positive.",
            code="ERR_RSTREAM_INVALID_TIMEOUT",
        )
    region = _normalize_region(
        _first_defined(options.region, env.region, config.region)
    )
    explicit_engine = _normalize_optional(_first_defined(options.engine, env.engine))
    project_endpoint = _normalize_optional(
        _first_defined(options.project_endpoint, config.project_endpoint)
    )
    if region is not None and explicit_engine is not None:
        raise ConfigurationError(
            "Region selection cannot be combined with an explicit engine override.",
            code="ERR_RSTREAM_REGION_ENGINE_CONFLICT",
        )
    if region is not None and project_endpoint is None:
        raise ConfigurationError(
            "Managed project endpoint is required for region selection.",
            code="ERR_RSTREAM_PROJECT_ENDPOINT_REQUIRED",
        )
    return ResolvedClientOptions(
        api_url=_first_defined(options.api_url, env.api_url, config.api_url)
        or DEFAULT_API_URL,
        control_plane_headers=dict(config.control_plane_headers),
        engine=normalize_engine_address(
            _first_defined(
                options.engine,
                env.engine,
                config.context_engine,
                config.engine,
            )
        ),
        connect_timeout=options.connect_timeout,
        heartbeat=options.heartbeat,
        heartbeat_interval=options.heartbeat_interval,
        operation_timeout=options.operation_timeout,
        no_token=options.no_token
        if options.no_token is not None
        else token is None and not _tls_has_client_certificate(tls),
        project_endpoint=project_endpoint,
        region=region,
        tls=tls,
        token=token,
        zero_rtt=options.zero_rtt,
        tunnel_transport="tls",
    )


def create_ssl_context(
    engine: str,
    options: TLSOptions | None,
    *,
    use_explicit_server_name: bool = True,
) -> tuple[ssl.SSLContext, str | None]:
    parsed_host = engine.split(":", 1)[0]
    server_name = (
        options.server_name
        if use_explicit_server_name and options is not None and options.server_name
        else parsed_host
    )
    context = ssl.create_default_context(cafile=options.ca_file if options else None)
    context.set_alpn_protocols(["rstrm/1"])
    if options and options.insecure_skip_verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    if options and options.cert_file and options.key_file:
        context.load_cert_chain(options.cert_file, options.key_file)
    elif options and (options.certificate or options.key):
        raise UnsupportedFeatureError(
            "Inline mTLS certificates are not supported by Python's ssl module. "
            "Use certificateFile and keyFile.",
            code="ERR_RSTREAM_UNSUPPORTED_MTLS_STORAGE",
        )
    return context, server_name


def normalize_engine_address(engine: str | None) -> str | None:
    normalized = _normalize_optional(engine)
    if normalized is None:
        return None
    if re.match(r"^[a-z][a-z0-9+.-]*://", normalized, re.I):
        raise ConfigurationError(
            "Engine must be a host[:port] value.",
            code="ERR_RSTREAM_INVALID_ENGINE",
        )
    if re.search(r"[/?#@\\\s]", normalized):
        raise ConfigurationError(
            "Engine must be a host[:port] value.",
            code="ERR_RSTREAM_INVALID_ENGINE",
        )
    parsed = urlparse(f"https://{normalized}")
    if parsed.username or parsed.password or parsed.path not in ("", "/"):
        raise ConfigurationError(
            "Engine must be a host[:port] value.",
            code="ERR_RSTREAM_INVALID_ENGINE",
        )
    if not _validate_hostname(parsed.hostname or ""):
        raise ConfigurationError(
            "Engine must use a valid hostname.",
            code="ERR_RSTREAM_INVALID_ENGINE",
        )
    if parsed.port is not None and not 1 <= parsed.port <= 65_535:
        raise ConfigurationError(
            "Engine port must be an integer between 1 and 65535.",
            code="ERR_RSTREAM_INVALID_ENGINE",
        )
    hostname = parsed.hostname
    if hostname is None:
        raise ConfigurationError(
            "Engine must use a valid hostname.",
            code="ERR_RSTREAM_INVALID_ENGINE",
        )
    return f"{hostname.lower()}{f':{parsed.port}' if parsed.port else ''}"


def _normalize_region(region: str | None) -> str | None:
    normalized = _normalize_optional(region)
    if normalized is None or normalized.lower() == "auto":
        return None
    value = normalized.lower()
    if len(value) > 64 or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?", value
    ):
        raise ConfigurationError(
            "Region can only contain letters, numbers, dots, underscores, or hyphens.",
            code="ERR_RSTREAM_INVALID_REGION",
        )
    return value


def _resolve_config(
    options: ClientOptions,
    env: _EnvSettings,
) -> _ResolvedConfig:
    if not options.read_config_file:
        return _ResolvedConfig(
            api_url=_first_defined(options.api_url, env.api_url) or DEFAULT_API_URL,
            control_plane_headers=_merge_control_plane_headers(
                env.control_plane_headers,
                options.control_plane_headers,
            ),
        )
    config_path = (
        _normalize_optional(_first_defined(options.config_path, env.config_path))
        or default_config_path()
    )
    config = _load_config(config_path)
    explicit_api_url = _normalize_api_url(_first_defined(options.api_url, env.api_url))
    context_name = _normalize_optional(
        _first_defined(options.context, env.context, config.default_context)
    )
    context = _find_context(config, context_name, explicit_api_url)
    context_api_url = context.api_url if context else None
    api_url = (
        _normalize_api_url(_first_defined(explicit_api_url, context_api_url))
        or DEFAULT_API_URL
    )
    environment = (
        _find_environment(config, api_url)
        if context is not None and context.api_url
        else None
    )
    explicit_engine = _normalize_optional(_first_defined(options.engine, env.engine))
    token = None if options.no_token else env.token
    if (
        token is None
        and not options.no_token
        and not _env_has_mtls(env)
        and not _tls_has_client_certificate(options.tls)
    ):
        token = _resolve_stored_token(context, environment)
    if (
        explicit_engine
        and token
        and options.token is None
        and env.token is None
        and _engine_override_uses_stored_auth(explicit_engine, context)
    ):
        raise ConfigurationError(
            "Refusing to use a stored token with an explicit engine override.",
            code="ERR_RSTREAM_STORED_TOKEN_ENGINE_OVERRIDE",
        )
    tls = _resolve_mtls_options(env, context, environment)
    if (
        explicit_engine
        and _tls_has_client_certificate(tls)
        and not _env_has_mtls(env)
        and not _tls_has_client_certificate(options.tls)
        and _engine_override_uses_stored_auth(explicit_engine, context)
    ):
        raise ConfigurationError(
            "Refusing to use stored mTLS credentials with an explicit engine override.",
            code="ERR_RSTREAM_STORED_MTLS_ENGINE_OVERRIDE",
        )
    environment_transport = environment.transport if environment else None
    context_transport = context.transport if context else None
    _reject_unsupported_transport(environment_transport)
    _reject_unsupported_transport(context_transport)
    tunnel_transport = _transport_mode_from_config(context_transport)
    if tunnel_transport is None:
        tunnel_transport = _transport_mode_from_config(environment_transport)
    return _ResolvedConfig(
        api_url=api_url,
        control_plane_headers=_merge_control_plane_headers(
            environment.headers if environment else None,
            env.control_plane_headers,
            options.control_plane_headers,
        ),
        context_engine=context.engine if context else None,
        engine=explicit_engine,
        project_endpoint=context.project_endpoint if context else None,
        region=context.region if context else None,
        tls=tls,
        token=token,
        tunnel_transport=tunnel_transport,
    )


def _read_env() -> _EnvSettings:
    legacy_quic = _normalize_optional(os.getenv("RSTREAM_QUIC_TRANSPORT"))
    return _EnvSettings(
        api_url=_normalize_api_url(os.getenv("RSTREAM_API_URL")),
        config_path=_normalize_optional(os.getenv("RSTREAM_CONFIG")),
        context=_normalize_optional(os.getenv("RSTREAM_CONTEXT")),
        control_plane_headers=_control_plane_headers_from_json(
            os.getenv("RSTREAM_CONTROL_PLANE_HEADERS")
        ),
        engine=_normalize_optional(
            _first_defined(
                os.getenv("RSTREAM_ENGINE"),
                os.getenv("RSTREAM_ENGINE_ADDRESS"),
            )
        ),
        mtls_cert=_normalize_optional(os.getenv("RSTREAM_MTLS_CERT_FILE")),
        mtls_key=_normalize_optional(os.getenv("RSTREAM_MTLS_KEY_FILE")),
        region=_normalize_optional(os.getenv("RSTREAM_REGION")),
        token=_normalize_optional(os.getenv("RSTREAM_AUTHENTICATION_TOKEN")),
        tunnel_transport=_normalize_optional(os.getenv("RSTREAM_TUNNEL_TRANSPORT")),
        use_quic=None if legacy_quic is None else legacy_quic == "1",
    )


def _load_config(path: str) -> _ConfigFile:
    try:
        content = Path(path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return _ConfigFile()
    if not content:
        return _ConfigFile()
    try:
        value = yaml.safe_load(content)
    except yaml.YAMLError as error:
        raise ConfigurationError(
            "Failed to parse rstream config file.",
            code="ERR_RSTREAM_INVALID_CONFIG",
        ) from error
    if not isinstance(value, Mapping):
        return _ConfigFile()
    return _normalize_config(value)


def _normalize_config(value: Mapping[object, object]) -> _ConfigFile:
    defaults = _record(value.get("defaults"))
    default_context = _record(defaults.get("context")) if defaults else None
    contexts = tuple(
        ctx
        for item in _records(value.get("contexts"))
        if (ctx := _context_config(item)).name
    )
    environments = tuple(
        env
        for item in _records(value.get("environments"))
        if (env := _environment_config(item)).api_url
    )
    return _ConfigFile(
        default_context=_normalize_optional(
            _string(default_context.get("name")) if default_context else None
        ),
        contexts=contexts,
        environments=environments,
    )


def _context_config(value: Mapping[str, object]) -> _ContextConfig:
    return _ContextConfig(
        name=_string(value.get("name")) or "",
        api_url=_normalize_api_url(_string(value.get("apiUrl"))),
        auth=_auth_config(value.get("auth")),
        engine=_normalize_optional(_string(value.get("engine"))),
        project_endpoint=_normalize_optional(_string(value.get("projectEndpoint"))),
        region=_normalize_optional(_string(value.get("region"))),
        transport=_transport_config(value.get("transport")),
    )


def _environment_config(value: Mapping[str, object]) -> _EnvironmentConfig:
    return _EnvironmentConfig(
        api_url=_normalize_api_url(_string(value.get("apiUrl"))) or "",
        auth=_auth_config(value.get("auth")),
        headers=_control_plane_headers_config(value.get("headers")),
        transport=_transport_config(value.get("transport")),
    )


def _auth_config(value: object) -> _AuthConfig | None:
    auth = _record(value)
    if auth is None:
        return None
    token = _record(auth.get("token"))
    storage = _record(token.get("storage")) if token else None
    mtls = _record(auth.get("mtls"))
    mtls_storage = _record(mtls.get("storage")) if mtls else None
    return _AuthConfig(
        token=_TokenConfig(
            value=_string(storage.get("value")) if storage else None,
            kind=_string(storage.get("kind")) if storage else None,
            provider=_string(storage.get("provider")) if storage else None,
            service=_string(storage.get("service")) if storage else None,
            account=_string(storage.get("account")) if storage else None,
        )
        if storage
        else None,
        mtls=_MTLSConfig(
            certificate=_string(mtls.get("certificate")),
            certificate_file=_string(mtls.get("certificateFile")),
            key=_string(mtls.get("key")),
            key_file=_string(mtls.get("keyFile")),
            storage=mtls_storage,
        )
        if mtls
        else None,
    )


def _transport_config(value: object) -> _TransportConfig | None:
    transport = _record(value)
    return None if transport is None else _TransportConfig(raw=dict(transport))


def _find_context(
    config: _ConfigFile,
    name: str | None,
    api_url: str | None,
) -> _ContextConfig | None:
    if name is None:
        return None
    matches = [
        ctx
        for ctx in config.contexts
        if ctx.name == name and (api_url is None or ctx.api_url in (None, api_url))
    ]
    if not matches:
        raise ConfigurationError(
            f"Context '{name}' was not found.",
            code="ERR_RSTREAM_CONTEXT_NOT_FOUND",
        )
    if len(matches) > 1:
        raise ConfigurationError(
            f"Context '{name}' is ambiguous for the selected API URL.",
            code="ERR_RSTREAM_CONTEXT_AMBIGUOUS",
        )
    return matches[0]


def _find_environment(
    config: _ConfigFile,
    api_url: str,
) -> _EnvironmentConfig | None:
    for environment in config.environments:
        if _normalize_api_url(environment.api_url) == api_url:
            return environment
    return None


def _resolve_stored_token(
    context: _ContextConfig | None,
    environment: _EnvironmentConfig | None,
) -> str | None:
    token = context.auth.token if context and context.auth else None
    if token is None and environment and environment.auth:
        token = environment.auth.token
    if token is None:
        return None
    provider = _normalize_optional(token.provider or token.kind)
    if provider and provider not in {"inline", "env"}:
        raise UnsupportedFeatureError(
            f"Token storage provider '{provider}' is not supported by rstream-python.",
            code="ERR_RSTREAM_UNSUPPORTED_TOKEN_STORAGE",
        )
    return token.value


def _resolve_mtls_options(
    env: _EnvSettings,
    context: _ContextConfig | None,
    environment: _EnvironmentConfig | None,
) -> TLSOptions | None:
    if env.mtls_cert or env.mtls_key:
        if not env.mtls_cert or not env.mtls_key:
            raise ConfigurationError(
                "Both RSTREAM_MTLS_CERT_FILE and RSTREAM_MTLS_KEY_FILE are required.",
                code="ERR_RSTREAM_MTLS_INCOMPLETE",
            )
        return TLSOptions(cert_file=env.mtls_cert, key_file=env.mtls_key)
    mtls = context.auth.mtls if context and context.auth else None
    if mtls is None and environment and environment.auth:
        mtls = environment.auth.mtls
    if mtls is None:
        return None
    if mtls.storage:
        provider = _normalize_optional(_string(mtls.storage.get("provider")))
        kind = _normalize_optional(_string(mtls.storage.get("kind")))
        label = provider or kind or "configured"
        raise UnsupportedFeatureError(
            f"mTLS storage provider '{label}' is not supported by rstream-python.",
            code="ERR_RSTREAM_UNSUPPORTED_MTLS_STORAGE",
        )
    if mtls.certificate_file or mtls.key_file:
        if not mtls.certificate_file or not mtls.key_file:
            raise ConfigurationError(
                "Both certificateFile and keyFile are required for mTLS.",
                code="ERR_RSTREAM_MTLS_INCOMPLETE",
            )
        return TLSOptions(cert_file=mtls.certificate_file, key_file=mtls.key_file)
    if mtls.certificate or mtls.key:
        if not mtls.certificate or not mtls.key:
            raise ConfigurationError(
                "Both certificate and key are required for mTLS.",
                code="ERR_RSTREAM_MTLS_INCOMPLETE",
            )
        return TLSOptions(certificate=mtls.certificate, key=mtls.key)
    return None


def _reject_unsupported_transport(transport: _TransportConfig | None) -> None:
    if transport is None or not transport.raw:
        return
    if "mode" in transport.raw:
        _parse_tunnel_transport_mode(transport.raw.get("mode"))
    unsupported = [
        key
        for key in ("bind", "dns", "ipFamily", "mptcp", "proxy")
        if key in transport.raw
    ]
    if unsupported:
        joined = ", ".join(sorted(unsupported))
        raise UnsupportedFeatureError(
            f"Transport option(s) not supported by rstream-python: {joined}.",
            code="ERR_RSTREAM_UNSUPPORTED_TRANSPORT",
        )


def _transport_mode_from_config(transport: _TransportConfig | None) -> str | None:
    if transport is None:
        return None
    if "mode" in transport.raw:
        return _parse_tunnel_transport_mode(transport.raw.get("mode"))
    if "useQuic" in transport.raw:
        value = transport.raw.get("useQuic")
        if not isinstance(value, bool):
            raise ConfigurationError(
                "transport.useQuic must be a boolean.",
                code="ERR_RSTREAM_INVALID_CONFIG",
            )
        return "quic" if value else "tls"
    return None


def _resolve_tunnel_transport_mode(
    explicit: str | None,
    environment: str | None,
    legacy_environment: bool | None,
    configured: str | None,
) -> str:
    direct = _first_defined(explicit, environment)
    if direct is not None:
        return _parse_tunnel_transport_mode(direct)
    if legacy_environment is not None:
        return "quic" if legacy_environment else "tls"
    return configured or "auto"


def _parse_tunnel_transport_mode(value: object) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(
            "transport.mode must be a string.", code="ERR_RSTREAM_INVALID_CONFIG"
        )
    mode = value.strip().lower()
    if mode not in {"auto", "tls", "quic"}:
        raise ConfigurationError(
            f'Invalid tunnel transport "{value}" (valid: auto, tls, quic).',
            code="ERR_RSTREAM_INVALID_CONFIG",
        )
    return mode


def _merge_tls_options(
    inherited: TLSOptions | None,
    explicit: TLSOptions | None,
) -> TLSOptions | None:
    if inherited is None:
        return explicit
    if explicit is None:
        return inherited
    return TLSOptions(
        ca_file=explicit.ca_file or inherited.ca_file,
        cert_file=explicit.cert_file or inherited.cert_file,
        key_file=explicit.key_file or inherited.key_file,
        certificate=explicit.certificate or inherited.certificate,
        key=explicit.key or inherited.key,
        server_name=explicit.server_name or inherited.server_name,
        insecure_skip_verify=explicit.insecure_skip_verify
        or inherited.insecure_skip_verify,
    )


def _merge_control_plane_headers(
    *sources: Mapping[str, str] | None,
) -> Mapping[str, str]:
    merged: dict[str, str] = {}
    for source in sources:
        merged.update(_normalize_control_plane_headers(source))
    return merged


def _control_plane_headers_from_json(value: str | None) -> Mapping[str, str]:
    normalized = _normalize_optional(value)
    if normalized is None:
        return {}
    try:
        parsed: object = json.loads(normalized)
    except json.JSONDecodeError as error:
        raise ConfigurationError(
            "RSTREAM_CONTROL_PLANE_HEADERS must be a JSON object of string values.",
            code="ERR_RSTREAM_INVALID_CONFIG",
        ) from error
    return _control_plane_headers_config(parsed)


def _control_plane_headers_config(value: object) -> Mapping[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigurationError(
            "Control plane headers must be an object of string values.",
            code="ERR_RSTREAM_INVALID_CONFIG",
        )
    headers: dict[str, str] = {}
    for name, header_value in value.items():
        if not isinstance(name, str) or not isinstance(header_value, str):
            raise ConfigurationError(
                "Control plane headers must be an object of string values.",
                code="ERR_RSTREAM_INVALID_CONFIG",
            )
        headers[name] = header_value
    return _normalize_control_plane_headers(headers)


def _normalize_control_plane_headers(
    headers: Mapping[str, str] | None,
) -> Mapping[str, str]:
    normalized: dict[str, str] = {}
    for raw_name, value in (headers or {}).items():
        if not isinstance(raw_name, str) or not isinstance(value, str):
            raise ConfigurationError(
                "Control plane headers must contain string names and values.",
                code="ERR_RSTREAM_INVALID_CONFIG",
            )
        name = raw_name.strip()
        lower_name = name.lower()
        if not _HEADER_NAME_PATTERN.fullmatch(name):
            raise ConfigurationError(
                f"Invalid control plane header name '{raw_name}'.",
                code="ERR_RSTREAM_INVALID_CONFIG",
            )
        if lower_name in _RESERVED_CONTROL_PLANE_HEADERS or lower_name.startswith(
            "x-forwarded-"
        ):
            raise ConfigurationError(
                f"Control plane header '{raw_name}' is reserved.",
                code="ERR_RSTREAM_INVALID_CONFIG",
            )
        if "\r" in value or "\n" in value:
            raise ConfigurationError(
                f"Control plane header '{raw_name}' has an invalid value.",
                code="ERR_RSTREAM_INVALID_CONFIG",
            )
        canonical_name = "-".join(
            part[:1].upper() + part[1:].lower() for part in name.split("-")
        )
        if canonical_name in normalized:
            raise ConfigurationError(
                f"Duplicate control plane header '{canonical_name}'.",
                code="ERR_RSTREAM_INVALID_CONFIG",
            )
        normalized[canonical_name] = value
    return normalized


def _validate_token_expiry(token: str) -> None:
    parts = token.split(".")
    if len(parts) < 2:
        return
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        value = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return
    exp = value.get("exp")
    if not isinstance(exp, int):
        return
    if exp <= int(__import__("time").time()):
        raise ConfigurationError(
            "Authentication token has expired.",
            code="ERR_RSTREAM_TOKEN_EXPIRED",
        )


def _engine_override_uses_stored_auth(
    explicit_engine: str,
    context: _ContextConfig | None,
) -> bool:
    if context is None:
        return True
    context_engine = normalize_engine_address(context.engine)
    explicit = normalize_engine_address(explicit_engine)
    return context_engine is None or context_engine != explicit


def _env_has_mtls(env: _EnvSettings) -> bool:
    return env.mtls_cert is not None or env.mtls_key is not None


def _tls_has_client_certificate(tls: TLSOptions | None) -> bool:
    if tls is None:
        return False
    return bool((tls.cert_file and tls.key_file) or (tls.certificate and tls.key))


def _normalize_api_url(value: str | None) -> str | None:
    normalized = _normalize_optional(value)
    if normalized is None:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError(
            "API URL must be an absolute HTTP(S) URL.",
            code="ERR_RSTREAM_INVALID_API_URL",
        )
    return normalized.rstrip("/")


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_hostname(hostname: str) -> bool:
    if not hostname or len(hostname) > 253 or ".." in hostname:
        return False
    return all(
        label == "localhost" or _DNS_LABEL_PATTERN.fullmatch(label)
        for label in hostname.split(".")
    )


def _record(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return None


def _records(value: object) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(record for item in value if (record := _record(item)) is not None)


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _first_defined(*values: str | None) -> str | None:
    for value in values:
        if value is not None:
            return value
    return None
