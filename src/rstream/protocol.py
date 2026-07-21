"""Runtime protocol framing and protobuf conversion."""

from __future__ import annotations

import asyncio
import platform
import struct
import sys
from datetime import datetime, timezone
from typing import Protocol, TypeVar, cast

from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.wrappers_pb2 import BoolValue, StringValue, UInt32Value

from rstream._proto import rstream_pb2 as pb
from rstream.errors import EngineError, ProtocolError
from rstream.types import (
    HTTPVersion,
    ServerDetails,
    TLSMode,
    TunnelProperties,
    TunnelProtocol,
    TunnelType,
)
from rstream.version import __version__

RUNTIME_AGENT = "rstream-python-runtime"
RUNTIME_CHANNEL = "sdk"
MAX_FRAME_SIZE = 65_535
PACKAGE_NAME = "rstreamlabs-rstream"

T = TypeVar("T")


class _HasFields(Protocol):
    def HasField(self, field_name: str) -> bool: ...


def package_version() -> str:
    return __version__


def protocol_version() -> str:
    value = pb.DESCRIPTOR.GetOptions().Extensions[pb.protocol_version]
    if not isinstance(value, str) or not value:
        raise ProtocolError(
            "Protocol version is missing from the protobuf descriptor.",
            code="ERR_RSTREAM_PROTOCOL",
        )
    return value


def string_value(value: str | None) -> StringValue | None:
    return None if value is None else StringValue(value=value)


def bool_value(value: bool | None) -> BoolValue | None:
    return None if value is None else BoolValue(value=value)


def uint32_value(value: int | None) -> UInt32Value | None:
    return None if value is None else UInt32Value(value=value)


def timestamp_value(value: datetime | None) -> Timestamp | None:
    if value is None:
        return None
    normalized = (
        value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    )
    timestamp = Timestamp()
    timestamp.FromDatetime(normalized.astimezone(timezone.utc))
    return timestamp


def wrapper_string(value: StringValue | None) -> str | None:
    return None if value is None else value.value


def wrapper_bool(value: BoolValue | None) -> bool | None:
    return None if value is None else value.value


def wrapper_uint32(value: UInt32Value | None) -> int | None:
    return None if value is None else value.value


def wrapper_datetime(value: Timestamp | None) -> datetime | None:
    if value is None:
        return None
    return cast(datetime, value.ToDatetime(tzinfo=timezone.utc))


def optional_field(
    message: _HasFields,
    field_name: str,
    expected_type: type[T],
) -> T | None:
    has_field = message.HasField
    if not has_field(field_name):
        return None
    value = getattr(message, field_name)
    if isinstance(value, expected_type):
        return value
    raise ProtocolError(
        f"Unexpected protobuf field type for {field_name}.",
        code="ERR_RSTREAM_PROTOCOL",
    )


def tunnel_properties_to_pb(properties: TunnelProperties) -> pb.TunnelProperties:
    result = pb.TunnelProperties()
    if properties.id is not None:
        result.id.CopyFrom(StringValue(value=properties.id))
    if properties.creation_date is not None:
        result.creation_date.CopyFrom(timestamp_value(properties.creation_date))
    if properties.name is not None:
        result.name.CopyFrom(StringValue(value=properties.name))
    if properties.type is not None:
        result.type.CopyFrom(StringValue(value=properties.type))
    if properties.publish is not None:
        result.publish.CopyFrom(BoolValue(value=properties.publish))
    if properties.protocol is not None:
        result.protocol.CopyFrom(StringValue(value=properties.protocol))
    result.labels.update(properties.labels)
    result.geoip.extend(properties.geo_ip)
    result.trusted_ips.extend(properties.trusted_ips)
    if properties.host is not None:
        result.host.CopyFrom(StringValue(value=properties.host))
    if properties.tls_mode is not None:
        result.tls_mode.CopyFrom(StringValue(value=properties.tls_mode))
    result.tls_alpns.extend(properties.tls_alpns)
    if properties.tls_min_version is not None:
        result.tls_min_version.CopyFrom(StringValue(value=properties.tls_min_version))
    result.tls_ciphers.extend(properties.tls_ciphers)
    if properties.mtls_auth is not None:
        result.mtls_auth.CopyFrom(BoolValue(value=properties.mtls_auth))
    if properties.http_version is not None:
        result.http_version.CopyFrom(StringValue(value=properties.http_version))
    if properties.http_use_tls is not None:
        result.http_use_tls.CopyFrom(BoolValue(value=properties.http_use_tls))
    if properties.token_auth is not None:
        result.token_auth.CopyFrom(BoolValue(value=properties.token_auth))
    if properties.rstream_auth is not None:
        result.rstream_auth.CopyFrom(BoolValue(value=properties.rstream_auth))
    if properties.challenge_mode is not None:
        result.challenge_mode.CopyFrom(BoolValue(value=properties.challenge_mode))
    if properties.hostname is not None:
        result.hostname.CopyFrom(StringValue(value=properties.hostname))
    if properties.port is not None:
        result.port.CopyFrom(UInt32Value(value=properties.port))
    if properties.upstream_tls is not None:
        result.upstream_tls.CopyFrom(BoolValue(value=properties.upstream_tls))
    if properties.datagram_guaranteed_delivery is not None:
        result.datagram_guaranteed_delivery.CopyFrom(
            BoolValue(value=properties.datagram_guaranteed_delivery)
        )
    if properties.allow_cross_region_routing is not None:
        result.allow_cross_region_routing.CopyFrom(
            BoolValue(value=properties.allow_cross_region_routing)
        )
    return result


def tunnel_properties_from_pb(properties: pb.TunnelProperties) -> TunnelProperties:
    return TunnelProperties(
        id=wrapper_string(optional_field(properties, "id", StringValue)),
        creation_date=wrapper_datetime(
            optional_field(properties, "creation_date", Timestamp)
        ),
        name=wrapper_string(optional_field(properties, "name", StringValue)),
        type=cast_tunnel_type(
            wrapper_string(optional_field(properties, "type", StringValue)),
        ),
        publish=wrapper_bool(optional_field(properties, "publish", BoolValue)),
        protocol=cast_protocol(
            wrapper_string(optional_field(properties, "protocol", StringValue)),
        ),
        labels=dict(properties.labels),
        geo_ip=tuple(properties.geoip),
        trusted_ips=tuple(properties.trusted_ips),
        host=wrapper_string(optional_field(properties, "host", StringValue)),
        tls_mode=cast_tls_mode(
            wrapper_string(optional_field(properties, "tls_mode", StringValue)),
        ),
        tls_alpns=tuple(properties.tls_alpns),
        tls_min_version=wrapper_string(
            optional_field(properties, "tls_min_version", StringValue)
        ),
        tls_ciphers=tuple(properties.tls_ciphers),
        mtls_auth=wrapper_bool(optional_field(properties, "mtls_auth", BoolValue)),
        http_version=cast_http_version(
            wrapper_string(optional_field(properties, "http_version", StringValue)),
        ),
        http_use_tls=wrapper_bool(
            optional_field(properties, "http_use_tls", BoolValue)
        ),
        token_auth=wrapper_bool(optional_field(properties, "token_auth", BoolValue)),
        rstream_auth=wrapper_bool(
            optional_field(properties, "rstream_auth", BoolValue)
        ),
        challenge_mode=wrapper_bool(
            optional_field(properties, "challenge_mode", BoolValue)
        ),
        hostname=wrapper_string(optional_field(properties, "hostname", StringValue)),
        port=wrapper_uint32(optional_field(properties, "port", UInt32Value)),
        upstream_tls=wrapper_bool(
            optional_field(properties, "upstream_tls", BoolValue)
        ),
        datagram_guaranteed_delivery=wrapper_bool(
            optional_field(properties, "datagram_guaranteed_delivery", BoolValue)
        ),
        allow_cross_region_routing=wrapper_bool(
            optional_field(properties, "allow_cross_region_routing", BoolValue)
        ),
    )


def server_details_from_pb(details: pb.ServerDetails | None) -> ServerDetails | None:
    if details is None:
        return None
    return ServerDetails(
        agent=wrapper_string(optional_field(details, "agent", StringValue)),
        channel=wrapper_string(optional_field(details, "channel", StringValue)),
        version=wrapper_string(optional_field(details, "version", StringValue)),
        plan=wrapper_string(optional_field(details, "plan", StringValue)),
        provider=wrapper_string(optional_field(details, "provider", StringValue)),
        region=wrapper_string(optional_field(details, "region", StringValue)),
        update=wrapper_string(optional_field(details, "update", StringValue)),
    )


def create_client_details(token: str | None) -> pb.ClientDetails:
    details = pb.ClientDetails()
    details.agent.CopyFrom(StringValue(value=RUNTIME_AGENT))
    details.channel.CopyFrom(StringValue(value=RUNTIME_CHANNEL))
    details.version.CopyFrom(StringValue(value=package_version()))
    details.os.CopyFrom(StringValue(value=sys.platform))
    details.arch.CopyFrom(StringValue(value=platform.machine()))
    details.protocol_version.CopyFrom(StringValue(value=protocol_version()))
    if token is not None:
        details.token.CopyFrom(StringValue(value=token))
    return details


def message_with_open_control_channel_req(token: str | None) -> pb.Message:
    message = pb.Message()
    message.open_control_channel_req.client_details.CopyFrom(
        create_client_details(token)
    )
    return message


def message_with_close_control_channel_req() -> pb.Message:
    message = pb.Message()
    message.close_control_channel_req.CopyFrom(pb.CloseControlChannelReq())
    return message


def message_with_open_tunnel_req(
    request_id: str,
    properties: TunnelProperties,
) -> pb.Message:
    message = pb.Message()
    message.open_tunnel_req.request_id = request_id
    message.open_tunnel_req.tunnel_properties.CopyFrom(
        tunnel_properties_to_pb(properties)
    )
    return message


def message_with_close_tunnel_req(tunnel_id: str) -> pb.Message:
    message = pb.Message()
    message.close_tunnel_req.tunnel_id = tunnel_id
    return message


def message_with_proxy_conn_rsp(
    stream_id: str,
    error: pb.Error | None = None,
) -> pb.Message:
    message = pb.Message()
    message.proxy_conn_rsp.stream_id = stream_id
    if error is not None:
        message.proxy_conn_rsp.error.CopyFrom(error)
    return message


def message_with_proxy_req(
    stream_id: str,
    token: str | None,
    zero_rtt: bool,
) -> pb.Message:
    message = pb.Message()
    message.proxy_req.client_details.CopyFrom(create_client_details(token))
    message.proxy_req.stream_id = stream_id
    message.proxy_req.zero_rtt.CopyFrom(BoolValue(value=zero_rtt))
    return message


def message_with_stream_req(
    tunnel_id_or_name: str,
    token: str | None,
    zero_rtt: bool,
) -> pb.Message:
    message = pb.Message()
    message.stream_req.client_details.CopyFrom(create_client_details(token))
    message.stream_req.tunnel_id_name = tunnel_id_or_name
    message.stream_req.zero_rtt.CopyFrom(BoolValue(value=zero_rtt))
    return message


def message_with_heartbeat() -> pb.Message:
    message = pb.Message()
    message.heartbeat.CopyFrom(pb.Heartbeat())
    return message


def engine_error_from_pb(error: pb.Error) -> EngineError:
    message = "Engine error."
    if error.HasField("message"):
        message = error.message.value
    return EngineError(int(error.code), message)


def error_to_pb(message: str) -> pb.Error:
    error = pb.Error()
    error.code = pb.ERROR_CODE_INVALID_STREAM
    error.message.CopyFrom(StringValue(value=message))
    return error


def encode_message(message: pb.Message) -> bytes:
    payload = cast(bytes, message.SerializeToString())
    if len(payload) > MAX_FRAME_SIZE:
        raise ProtocolError(
            f"Protocol frame too large: {len(payload)} bytes.",
            code="ERR_RSTREAM_FRAME_TOO_LARGE",
        )
    return struct.pack(">I", len(payload)) + payload


def decode_message(payload: bytes) -> pb.Message:
    message = pb.Message()
    message.ParseFromString(payload)
    return message


async def write_message(writer: asyncio.StreamWriter, message: pb.Message) -> None:
    writer.write(encode_message(message))
    await writer.drain()


async def read_message(reader: asyncio.StreamReader) -> pb.Message:
    header = await reader.readexactly(4)
    frame_size = struct.unpack(">I", header)[0]
    if frame_size > MAX_FRAME_SIZE:
        raise ProtocolError(
            f"Protocol frame too large: {frame_size} bytes.",
            code="ERR_RSTREAM_FRAME_TOO_LARGE",
        )
    return decode_message(await reader.readexactly(frame_size))


def cast_tunnel_type(value: str | None) -> TunnelType | None:
    if value == "bytestream" or value == "datagram":
        return cast(TunnelType, value)
    return None


def cast_protocol(value: str | None) -> TunnelProtocol | None:
    if value in {"tls", "tcp", "dtls", "quic", "http"}:
        return cast(TunnelProtocol, value)
    return None


def cast_http_version(value: str | None) -> HTTPVersion | None:
    if value in {"http/1.1", "h2", "h2c", "h3"}:
        return cast(HTTPVersion, value)
    return None


def cast_tls_mode(value: str | None) -> TLSMode | None:
    if value == "passthrough" or value == "terminated":
        return cast(TLSMode, value)
    return None
