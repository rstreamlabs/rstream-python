import datetime

from google.protobuf import descriptor_pb2 as _descriptor_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ErrorCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ERROR_CODE_UNSPECIFIED: _ClassVar[ErrorCode]
    ERROR_CODE_UNAUTHORIZED: _ClassVar[ErrorCode]
    ERROR_CODE_INVALID_REQUEST: _ClassVar[ErrorCode]
    ERROR_CODE_PROTOCOL_VERSION_MISSING: _ClassVar[ErrorCode]
    ERROR_CODE_PROTOCOL_VERSION_INVALID: _ClassVar[ErrorCode]
    ERROR_CODE_PROTOCOL_VERSION_INCOMPATIBLE: _ClassVar[ErrorCode]
    ERROR_CODE_TUNNEL_NOT_FOUND: _ClassVar[ErrorCode]
    ERROR_CODE_INVALID_STREAM: _ClassVar[ErrorCode]
    ERROR_CODE_FEATURE_NOT_AVAILABLE: _ClassVar[ErrorCode]
    ERROR_CODE_SERVICE_UNAVAILABLE: _ClassVar[ErrorCode]
    ERROR_CODE_INTERNAL: _ClassVar[ErrorCode]
ERROR_CODE_UNSPECIFIED: ErrorCode
ERROR_CODE_UNAUTHORIZED: ErrorCode
ERROR_CODE_INVALID_REQUEST: ErrorCode
ERROR_CODE_PROTOCOL_VERSION_MISSING: ErrorCode
ERROR_CODE_PROTOCOL_VERSION_INVALID: ErrorCode
ERROR_CODE_PROTOCOL_VERSION_INCOMPATIBLE: ErrorCode
ERROR_CODE_TUNNEL_NOT_FOUND: ErrorCode
ERROR_CODE_INVALID_STREAM: ErrorCode
ERROR_CODE_FEATURE_NOT_AVAILABLE: ErrorCode
ERROR_CODE_SERVICE_UNAVAILABLE: ErrorCode
ERROR_CODE_INTERNAL: ErrorCode
PROTOCOL_VERSION_FIELD_NUMBER: _ClassVar[int]
protocol_version: _descriptor.FieldDescriptor
ACCESS_FIELD_NUMBER: _ClassVar[int]
access: _descriptor.FieldDescriptor

class IpAddress(_message.Message):
    __slots__ = ("v4", "v6")
    V4_FIELD_NUMBER: _ClassVar[int]
    V6_FIELD_NUMBER: _ClassVar[int]
    v4: int
    v6: bytes
    def __init__(self, v4: _Optional[int] = ..., v6: _Optional[bytes] = ...) -> None: ...

class Error(_message.Message):
    __slots__ = ("code", "message")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    message: _wrappers_pb2.StringValue
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ..., message: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class ClientDetails(_message.Message):
    __slots__ = ("agent", "channel", "version", "os", "arch", "token", "protocol_version")
    AGENT_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    OS_FIELD_NUMBER: _ClassVar[int]
    ARCH_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_VERSION_FIELD_NUMBER: _ClassVar[int]
    agent: _wrappers_pb2.StringValue
    channel: _wrappers_pb2.StringValue
    version: _wrappers_pb2.StringValue
    os: _wrappers_pb2.StringValue
    arch: _wrappers_pb2.StringValue
    token: _wrappers_pb2.StringValue
    protocol_version: _wrappers_pb2.StringValue
    def __init__(self, agent: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., channel: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., os: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., arch: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., token: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., protocol_version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class ServerDetails(_message.Message):
    __slots__ = ("agent", "channel", "version", "plan", "provider", "region", "update")
    AGENT_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    PLAN_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    UPDATE_FIELD_NUMBER: _ClassVar[int]
    agent: _wrappers_pb2.StringValue
    channel: _wrappers_pb2.StringValue
    version: _wrappers_pb2.StringValue
    plan: _wrappers_pb2.StringValue
    provider: _wrappers_pb2.StringValue
    region: _wrappers_pb2.StringValue
    update: _wrappers_pb2.StringValue
    def __init__(self, agent: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., channel: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., plan: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., provider: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., region: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., update: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class TunnelProperties(_message.Message):
    __slots__ = ("id", "creation_date", "name", "type", "publish", "protocol", "labels", "geoip", "trusted_ips", "host", "tls_mode", "tls_alpns", "tls_min_version", "tls_ciphers", "mtls_auth", "mtls_cacert_pem", "http_version", "http_use_tls", "token_auth", "rstream_auth", "challenge_mode", "hostname", "port", "upstream_tls", "datagram_guaranteed_delivery")
    class LabelsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    ID_FIELD_NUMBER: _ClassVar[int]
    CREATION_DATE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PUBLISH_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    LABELS_FIELD_NUMBER: _ClassVar[int]
    GEOIP_FIELD_NUMBER: _ClassVar[int]
    TRUSTED_IPS_FIELD_NUMBER: _ClassVar[int]
    HOST_FIELD_NUMBER: _ClassVar[int]
    TLS_MODE_FIELD_NUMBER: _ClassVar[int]
    TLS_ALPNS_FIELD_NUMBER: _ClassVar[int]
    TLS_MIN_VERSION_FIELD_NUMBER: _ClassVar[int]
    TLS_CIPHERS_FIELD_NUMBER: _ClassVar[int]
    MTLS_AUTH_FIELD_NUMBER: _ClassVar[int]
    MTLS_CACERT_PEM_FIELD_NUMBER: _ClassVar[int]
    HTTP_VERSION_FIELD_NUMBER: _ClassVar[int]
    HTTP_USE_TLS_FIELD_NUMBER: _ClassVar[int]
    TOKEN_AUTH_FIELD_NUMBER: _ClassVar[int]
    RSTREAM_AUTH_FIELD_NUMBER: _ClassVar[int]
    CHALLENGE_MODE_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    UPSTREAM_TLS_FIELD_NUMBER: _ClassVar[int]
    DATAGRAM_GUARANTEED_DELIVERY_FIELD_NUMBER: _ClassVar[int]
    id: _wrappers_pb2.StringValue
    creation_date: _timestamp_pb2.Timestamp
    name: _wrappers_pb2.StringValue
    type: _wrappers_pb2.StringValue
    publish: _wrappers_pb2.BoolValue
    protocol: _wrappers_pb2.StringValue
    labels: _containers.ScalarMap[str, str]
    geoip: _containers.RepeatedScalarFieldContainer[str]
    trusted_ips: _containers.RepeatedScalarFieldContainer[str]
    host: _wrappers_pb2.StringValue
    tls_mode: _wrappers_pb2.StringValue
    tls_alpns: _containers.RepeatedScalarFieldContainer[str]
    tls_min_version: _wrappers_pb2.StringValue
    tls_ciphers: _containers.RepeatedScalarFieldContainer[str]
    mtls_auth: _wrappers_pb2.BoolValue
    mtls_cacert_pem: _wrappers_pb2.StringValue
    http_version: _wrappers_pb2.StringValue
    http_use_tls: _wrappers_pb2.BoolValue
    token_auth: _wrappers_pb2.BoolValue
    rstream_auth: _wrappers_pb2.BoolValue
    challenge_mode: _wrappers_pb2.BoolValue
    hostname: _wrappers_pb2.StringValue
    port: _wrappers_pb2.UInt32Value
    upstream_tls: _wrappers_pb2.BoolValue
    datagram_guaranteed_delivery: _wrappers_pb2.BoolValue
    def __init__(self, id: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., creation_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., name: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., type: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., publish: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., protocol: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., labels: _Optional[_Mapping[str, str]] = ..., geoip: _Optional[_Iterable[str]] = ..., trusted_ips: _Optional[_Iterable[str]] = ..., host: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., tls_mode: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., tls_alpns: _Optional[_Iterable[str]] = ..., tls_min_version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., tls_ciphers: _Optional[_Iterable[str]] = ..., mtls_auth: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., mtls_cacert_pem: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., http_version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., http_use_tls: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., token_auth: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., rstream_auth: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., challenge_mode: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., hostname: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., port: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., upstream_tls: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., datagram_guaranteed_delivery: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...

class OpenControlChannelReq(_message.Message):
    __slots__ = ("client_details",)
    CLIENT_DETAILS_FIELD_NUMBER: _ClassVar[int]
    client_details: ClientDetails
    def __init__(self, client_details: _Optional[_Union[ClientDetails, _Mapping]] = ...) -> None: ...

class OpenControlChannelRsp(_message.Message):
    __slots__ = ("ok", "error")
    class Ok(_message.Message):
        __slots__ = ("client_id", "server_details")
        CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
        SERVER_DETAILS_FIELD_NUMBER: _ClassVar[int]
        client_id: str
        server_details: ServerDetails
        def __init__(self, client_id: _Optional[str] = ..., server_details: _Optional[_Union[ServerDetails, _Mapping]] = ...) -> None: ...
    OK_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ok: OpenControlChannelRsp.Ok
    error: Error
    def __init__(self, ok: _Optional[_Union[OpenControlChannelRsp.Ok, _Mapping]] = ..., error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class CloseControlChannelReq(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CloseControlChannelRsp(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class OpenTunnelReq(_message.Message):
    __slots__ = ("request_id", "tunnel_properties")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TUNNEL_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    tunnel_properties: TunnelProperties
    def __init__(self, request_id: _Optional[str] = ..., tunnel_properties: _Optional[_Union[TunnelProperties, _Mapping]] = ...) -> None: ...

class OpenTunnelRsp(_message.Message):
    __slots__ = ("request_id", "tunnel_properties", "error")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TUNNEL_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    tunnel_properties: TunnelProperties
    error: Error
    def __init__(self, request_id: _Optional[str] = ..., tunnel_properties: _Optional[_Union[TunnelProperties, _Mapping]] = ..., error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class CloseTunnelReq(_message.Message):
    __slots__ = ("tunnel_id",)
    TUNNEL_ID_FIELD_NUMBER: _ClassVar[int]
    tunnel_id: str
    def __init__(self, tunnel_id: _Optional[str] = ...) -> None: ...

class CloseTunnelRsp(_message.Message):
    __slots__ = ("tunnel_id",)
    TUNNEL_ID_FIELD_NUMBER: _ClassVar[int]
    tunnel_id: str
    def __init__(self, tunnel_id: _Optional[str] = ...) -> None: ...

class ProxyConnReq(_message.Message):
    __slots__ = ("tunnel_id", "stream_id", "secret", "source_ip")
    TUNNEL_ID_FIELD_NUMBER: _ClassVar[int]
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    SECRET_FIELD_NUMBER: _ClassVar[int]
    SOURCE_IP_FIELD_NUMBER: _ClassVar[int]
    tunnel_id: str
    stream_id: str
    secret: _wrappers_pb2.StringValue
    source_ip: IpAddress
    def __init__(self, tunnel_id: _Optional[str] = ..., stream_id: _Optional[str] = ..., secret: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., source_ip: _Optional[_Union[IpAddress, _Mapping]] = ...) -> None: ...

class ProxyConnRsp(_message.Message):
    __slots__ = ("stream_id", "error")
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    stream_id: str
    error: Error
    def __init__(self, stream_id: _Optional[str] = ..., error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class ProxyReq(_message.Message):
    __slots__ = ("client_details", "stream_id", "zero_rtt")
    CLIENT_DETAILS_FIELD_NUMBER: _ClassVar[int]
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    ZERO_RTT_FIELD_NUMBER: _ClassVar[int]
    client_details: ClientDetails
    stream_id: str
    zero_rtt: _wrappers_pb2.BoolValue
    def __init__(self, client_details: _Optional[_Union[ClientDetails, _Mapping]] = ..., stream_id: _Optional[str] = ..., zero_rtt: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...

class ProxyRsp(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: Error
    def __init__(self, error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class StreamReq(_message.Message):
    __slots__ = ("client_details", "tunnel_id_name", "zero_rtt", "datagram_channel")
    CLIENT_DETAILS_FIELD_NUMBER: _ClassVar[int]
    TUNNEL_ID_NAME_FIELD_NUMBER: _ClassVar[int]
    ZERO_RTT_FIELD_NUMBER: _ClassVar[int]
    DATAGRAM_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    client_details: ClientDetails
    tunnel_id_name: str
    zero_rtt: _wrappers_pb2.BoolValue
    datagram_channel: _wrappers_pb2.BoolValue
    def __init__(self, client_details: _Optional[_Union[ClientDetails, _Mapping]] = ..., tunnel_id_name: _Optional[str] = ..., zero_rtt: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., datagram_channel: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...

class StreamRsp(_message.Message):
    __slots__ = ("stream_id", "error")
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    stream_id: str
    error: Error
    def __init__(self, stream_id: _Optional[str] = ..., error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class DatagramChannelClose(_message.Message):
    __slots__ = ("stream_id", "error")
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    stream_id: str
    error: Error
    def __init__(self, stream_id: _Optional[str] = ..., error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class Heartbeat(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ServerMessage(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class Message(_message.Message):
    __slots__ = ("open_control_channel_req", "open_control_channel_rsp", "close_control_channel_req", "close_control_channel_rsp", "open_tunnel_req", "open_tunnel_rsp", "close_tunnel_req", "close_tunnel_rsp", "proxy_conn_req", "proxy_conn_rsp", "proxy_req", "proxy_rsp", "stream_req", "stream_rsp", "heartbeat", "server_message", "datagram_channel_close")
    OPEN_CONTROL_CHANNEL_REQ_FIELD_NUMBER: _ClassVar[int]
    OPEN_CONTROL_CHANNEL_RSP_FIELD_NUMBER: _ClassVar[int]
    CLOSE_CONTROL_CHANNEL_REQ_FIELD_NUMBER: _ClassVar[int]
    CLOSE_CONTROL_CHANNEL_RSP_FIELD_NUMBER: _ClassVar[int]
    OPEN_TUNNEL_REQ_FIELD_NUMBER: _ClassVar[int]
    OPEN_TUNNEL_RSP_FIELD_NUMBER: _ClassVar[int]
    CLOSE_TUNNEL_REQ_FIELD_NUMBER: _ClassVar[int]
    CLOSE_TUNNEL_RSP_FIELD_NUMBER: _ClassVar[int]
    PROXY_CONN_REQ_FIELD_NUMBER: _ClassVar[int]
    PROXY_CONN_RSP_FIELD_NUMBER: _ClassVar[int]
    PROXY_REQ_FIELD_NUMBER: _ClassVar[int]
    PROXY_RSP_FIELD_NUMBER: _ClassVar[int]
    STREAM_REQ_FIELD_NUMBER: _ClassVar[int]
    STREAM_RSP_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    SERVER_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DATAGRAM_CHANNEL_CLOSE_FIELD_NUMBER: _ClassVar[int]
    open_control_channel_req: OpenControlChannelReq
    open_control_channel_rsp: OpenControlChannelRsp
    close_control_channel_req: CloseControlChannelReq
    close_control_channel_rsp: CloseControlChannelRsp
    open_tunnel_req: OpenTunnelReq
    open_tunnel_rsp: OpenTunnelRsp
    close_tunnel_req: CloseTunnelReq
    close_tunnel_rsp: CloseTunnelRsp
    proxy_conn_req: ProxyConnReq
    proxy_conn_rsp: ProxyConnRsp
    proxy_req: ProxyReq
    proxy_rsp: ProxyRsp
    stream_req: StreamReq
    stream_rsp: StreamRsp
    heartbeat: Heartbeat
    server_message: ServerMessage
    datagram_channel_close: DatagramChannelClose
    def __init__(self, open_control_channel_req: _Optional[_Union[OpenControlChannelReq, _Mapping]] = ..., open_control_channel_rsp: _Optional[_Union[OpenControlChannelRsp, _Mapping]] = ..., close_control_channel_req: _Optional[_Union[CloseControlChannelReq, _Mapping]] = ..., close_control_channel_rsp: _Optional[_Union[CloseControlChannelRsp, _Mapping]] = ..., open_tunnel_req: _Optional[_Union[OpenTunnelReq, _Mapping]] = ..., open_tunnel_rsp: _Optional[_Union[OpenTunnelRsp, _Mapping]] = ..., close_tunnel_req: _Optional[_Union[CloseTunnelReq, _Mapping]] = ..., close_tunnel_rsp: _Optional[_Union[CloseTunnelRsp, _Mapping]] = ..., proxy_conn_req: _Optional[_Union[ProxyConnReq, _Mapping]] = ..., proxy_conn_rsp: _Optional[_Union[ProxyConnRsp, _Mapping]] = ..., proxy_req: _Optional[_Union[ProxyReq, _Mapping]] = ..., proxy_rsp: _Optional[_Union[ProxyRsp, _Mapping]] = ..., stream_req: _Optional[_Union[StreamReq, _Mapping]] = ..., stream_rsp: _Optional[_Union[StreamRsp, _Mapping]] = ..., heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., server_message: _Optional[_Union[ServerMessage, _Mapping]] = ..., datagram_channel_close: _Optional[_Union[DatagramChannelClose, _Mapping]] = ...) -> None: ...
