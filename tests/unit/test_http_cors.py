from __future__ import annotations

import pytest

from rstream import HTTPCORS, CreateTunnelOptions, TunnelProperties
from rstream._proto import rstream_pb2 as pb
from rstream.control import _normalize_bytestream_options
from rstream.engine_api import tunnel_properties_from_json
from rstream.errors import RuntimeError
from rstream.protocol import tunnel_properties_from_pb, tunnel_properties_to_pb


def test_policy_round_trip_and_absence() -> None:
    policy = HTTPCORS(
        allowed_origins=("https://dashboard.example",),
        allowed_methods=("GET", "PUT"),
        allowed_headers=("Authorization",),
        exposed_headers=("ETag",),
        allow_credentials=True,
        max_age=600,
    )
    properties = _normalize_bytestream_options(CreateTunnelOptions(http_cors=policy))
    wire = tunnel_properties_to_pb(properties).SerializeToString()
    decoded = tunnel_properties_from_pb(pb.TunnelProperties.FromString(wire))
    assert decoded.http_cors == policy
    assert not tunnel_properties_to_pb(TunnelProperties()).HasField("http_cors")
    assert tunnel_properties_from_pb(pb.TunnelProperties()).http_cors is None
    assert tunnel_properties_from_json(
        {
            "http_cors": {
                "allowed_origins": ["https://dashboard.example"],
                "max_age": 120,
            }
        }
    ).http_cors == HTTPCORS(("https://dashboard.example",), max_age=120)
    assert tunnel_properties_from_json({}).http_cors is None


@pytest.mark.parametrize(
    "options",
    [
        CreateTunnelOptions(
            protocol="tls", http_cors=HTTPCORS(("https://dashboard.example",))
        ),
        CreateTunnelOptions(
            publish=False, http_cors=HTTPCORS(("https://dashboard.example",))
        ),
    ],
)
def test_policy_requires_published_http(options: CreateTunnelOptions) -> None:
    with pytest.raises(RuntimeError, match="published HTTP"):
        _normalize_bytestream_options(options)
