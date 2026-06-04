from __future__ import annotations

import pytest

import rstream


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
