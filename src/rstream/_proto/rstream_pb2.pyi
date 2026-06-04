from __future__ import annotations

from google.protobuf.descriptor import FieldDescriptor, FileDescriptor
from google.protobuf.message import Message as _PBMessage
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.wrappers_pb2 import BoolValue, StringValue, UInt32Value

DESCRIPTOR: FileDescriptor
ERROR_CODE_INVALID_STREAM: int
PROTOCOL_VERSION_FIELD_NUMBER: int
protocol_version: FieldDescriptor

class Error(_PBMessage):
    code: int
    message: StringValue

    def HasField(self, field_name: str) -> bool: ...

class ClientDetails(_PBMessage):
    agent: StringValue
    channel: StringValue
    version: StringValue
    os: StringValue
    arch: StringValue
    token: StringValue
    protocol_version: StringValue

class ServerDetails(_PBMessage):
    agent: StringValue
    channel: StringValue
    version: StringValue
    plan: StringValue
    provider: StringValue
    region: StringValue
    update: StringValue

    def HasField(self, field_name: str) -> bool: ...

class TunnelProperties(_PBMessage):
    id: StringValue
    creation_date: Timestamp
    name: StringValue
    type: StringValue
    publish: BoolValue
    protocol: StringValue
    labels: dict[str, str]
    geoip: list[str]
    trusted_ips: list[str]
    host: StringValue
    tls_mode: StringValue
    tls_alpns: list[str]
    tls_min_version: StringValue
    tls_ciphers: list[str]
    mtls_auth: BoolValue
    http_version: StringValue
    http_use_tls: BoolValue
    token_auth: BoolValue
    rstream_auth: BoolValue
    challenge_mode: BoolValue
    hostname: StringValue
    port: UInt32Value
    upstream_tls: BoolValue

    def HasField(self, field_name: str) -> bool: ...

class OpenControlChannelReq(_PBMessage):
    client_details: ClientDetails

class OpenControlChannelRsp(_PBMessage):
    class Ok(_PBMessage):
        client_id: str
        server_details: ServerDetails

    ok: Ok
    error: Error

    def WhichOneof(self, group_name: str) -> str | None: ...

class CloseControlChannelReq(_PBMessage): ...
class CloseControlChannelRsp(_PBMessage): ...

class OpenTunnelReq(_PBMessage):
    request_id: str
    tunnel_properties: TunnelProperties

class OpenTunnelRsp(_PBMessage):
    request_id: str
    tunnel_properties: TunnelProperties
    error: Error

    def WhichOneof(self, group_name: str) -> str | None: ...

class CloseTunnelReq(_PBMessage):
    tunnel_id: str

class CloseTunnelRsp(_PBMessage):
    tunnel_id: str

class ProxyConnReq(_PBMessage):
    tunnel_id: str
    stream_id: str
    secret: StringValue

    def HasField(self, field_name: str) -> bool: ...

class ProxyConnRsp(_PBMessage):
    stream_id: str
    error: Error

class ProxyReq(_PBMessage):
    client_details: ClientDetails
    stream_id: str
    zero_rtt: BoolValue

class ProxyRsp(_PBMessage):
    error: Error

    def HasField(self, field_name: str) -> bool: ...

class StreamReq(_PBMessage):
    client_details: ClientDetails
    tunnel_id_name: str
    zero_rtt: BoolValue

class StreamRsp(_PBMessage):
    stream_id: str
    error: Error

    def WhichOneof(self, group_name: str) -> str | None: ...

class Heartbeat(_PBMessage): ...

class Message(_PBMessage):
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

    def WhichOneof(self, group_name: str) -> str | None: ...
