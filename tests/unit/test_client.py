from __future__ import annotations

import pytest

import rstream
from rstream.api import RstreamAPIClient, TunnelsProject, TunnelsProjectRegionalEndpoint


@pytest.mark.asyncio
async def test_client_rejects_operations_after_close() -> None:
    client = rstream.Client(
        engine="localhost:9443",
        no_token=True,
        read_config_file=False,
    )

    await client.close()

    with pytest.raises(rstream.RstreamRuntimeError, match="client is closed") as exc:
        await client.connect()

    assert exc.value.code == "ERR_RSTREAM_CLIENT_CLOSED"

    with pytest.raises(rstream.RstreamRuntimeError, match="client is closed") as exc:
        await client.dial("private-api")

    assert exc.value.code == "ERR_RSTREAM_CLIENT_CLOSED"


@pytest.mark.asyncio
async def test_with_options_preserves_timeout_overrides() -> None:
    client = rstream.Client(
        connect_timeout=1.5,
        operation_timeout=2.5,
        read_config_file=False,
    )
    updated = client.with_options(engine="localhost:9443", no_token=True)
    resolved = await updated._get_resolved()

    assert resolved.engine == "localhost:9443"
    assert resolved.connect_timeout == 1.5
    assert resolved.operation_timeout == 2.5


@pytest.mark.asyncio
async def test_stable_hostname_uses_public_domain_with_regional_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = TunnelsProject(
        id="test-id",
        endpoint="abc123",
        url=None,
        domain="global.example.test",
        engine_port=443,
        routing="global",
        regional_endpoints=(
            TunnelsProjectRegionalEndpoint(
                provider="aws",
                region="eu-west-3",
                domain="paris.example.test",
                engine_port=8443,
            ),
        ),
    )

    async def lookup(_self: RstreamAPIClient, endpoint: str) -> TunnelsProject:
        assert endpoint == project.endpoint
        return project

    monkeypatch.setattr(RstreamAPIClient, "resolve_tunnels_project", lookup)
    async with rstream.Client(
        project_endpoint=project.endpoint, region="eu-west-3", read_config_file=False
    ) as client:
        resolved = await client._get_resolved()
        assert (
            await client._resolve_engine(resolved) == "abc123.paris.example.test:8443"
        )
        hostname = await client.generate_stable_hostname()
        assert hostname is not None and hostname.endswith(
            "-abc123.t.global.example.test"
        )

    async with rstream.Client(
        project_endpoint=project.endpoint, region="us-east-1", read_config_file=False
    ) as client:
        with pytest.raises(rstream.ConfigurationError, match="not available"):
            await client.generate_stable_hostname()
