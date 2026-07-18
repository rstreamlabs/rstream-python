from __future__ import annotations

import asyncio
import struct

import pytest

from rstream._proto import rstream_pb2 as pb
from rstream.protocol import (
    create_client_details,
    decode_message,
    encode_message,
    protocol_version,
    read_message,
    tunnel_properties_from_pb,
    tunnel_properties_to_pb,
)
from rstream.types import TunnelProperties
from rstream.version import __version__


def test_tunnel_properties_round_trip() -> None:
    properties = TunnelProperties(
        id="tun_123",
        name="api",
        type="bytestream",
        publish=True,
        protocol="http",
        labels={"service": "api"},
        http_version="http/1.1",
        token_auth=True,
        rstream_auth=True,
        hostname="api.example.test",
        port=443,
        datagram_guaranteed_delivery=True,
    )

    decoded = tunnel_properties_from_pb(tunnel_properties_to_pb(properties))

    assert decoded.id == "tun_123"
    assert decoded.name == "api"
    assert decoded.type == "bytestream"
    assert decoded.protocol == "http"
    assert decoded.labels == {"service": "api"}
    assert decoded.http_version == "http/1.1"
    assert decoded.token_auth is True
    assert decoded.rstream_auth is True
    assert decoded.hostname == "api.example.test"
    assert decoded.port == 443
    assert decoded.datagram_guaranteed_delivery is True


def test_published_tcp_properties_round_trip() -> None:
    properties = TunnelProperties(
        type="bytestream",
        publish=True,
        protocol="tcp",
        port=10042,
    )

    decoded = tunnel_properties_from_pb(tunnel_properties_to_pb(properties))

    assert decoded.protocol == "tcp"
    assert decoded.port == 10042


def test_message_encoding_prefixes_payload_length() -> None:
    message = pb.Message()
    message.heartbeat.CopyFrom(pb.Heartbeat())

    encoded = encode_message(message)
    decoded_size = struct.unpack(">I", encoded[:4])[0]

    assert decoded_size == len(encoded) - 4
    assert decode_message(encoded[4:]).WhichOneof("payload") == "heartbeat"


def test_client_details_use_protocol_version_from_proto_descriptor() -> None:
    expected = pb.DESCRIPTOR.GetOptions().Extensions[pb.protocol_version]
    details = create_client_details(None)

    assert protocol_version() == expected
    assert details.protocol_version.value == expected
    assert details.version.value == __version__
    assert __version__ != "unknown"


@pytest.mark.asyncio
async def test_read_message_rejects_oversized_frame() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(struct.pack(">I", 65_536))
    reader.feed_eof()

    with pytest.raises(Exception, match="Protocol frame too large"):
        await read_message(reader)
