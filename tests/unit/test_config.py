from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from rstream.config import (
    ClientOptions,
    normalize_engine_address,
    resolve_client_options,
)
from rstream.errors import ConfigurationError


def test_default_runtime_timeouts_are_resolved() -> None:
    resolved = asyncio.run(
        resolve_client_options(ClientOptions(read_config_file=False, no_token=True))
    )

    assert resolved.connect_timeout == 15.0
    assert resolved.operation_timeout == 30.0


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (
            ClientOptions(connect_timeout=0, read_config_file=False),
            "connect_timeout",
        ),
        (
            ClientOptions(connect_timeout=-1, read_config_file=False),
            "connect_timeout",
        ),
        (
            ClientOptions(operation_timeout=0, read_config_file=False),
            "operation_timeout",
        ),
        (
            ClientOptions(operation_timeout=-1, read_config_file=False),
            "operation_timeout",
        ),
    ],
)
def test_resolve_client_options_rejects_invalid_timeouts(
    options: ClientOptions,
    message: str,
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        asyncio.run(resolve_client_options(options))


def test_normalize_engine_address_rejects_credentials() -> None:
    with pytest.raises(Exception, match=r"host\[:port\]"):
        normalize_engine_address("user:pass@example.test:443")


def test_normalize_engine_address_rejects_scheme() -> None:
    with pytest.raises(Exception, match=r"host\[:port\]"):
        normalize_engine_address("https://example.test")


def test_resolve_config_file_context(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        """
version: 1
defaults:
  context:
    name: local
contexts:
  - name: local
    apiUrl: http://localhost:3000
    engine: c.localhost.rstream.io:9443
    auth:
      token:
        storage:
          value: local-token
""".strip(),
        encoding="utf-8",
    )

    resolved = asyncio.run(
        resolve_client_options(ClientOptions(config_path=str(config)))
    )

    assert resolved.api_url == "http://localhost:3000"
    assert resolved.engine == "c.localhost.rstream.io:9443"
    assert resolved.token == "local-token"


def test_resolve_config_rejects_invalid_yaml(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("contexts: [", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="parse rstream config"):
        asyncio.run(resolve_client_options(ClientOptions(config_path=str(config))))


def test_no_token_skips_stored_config_token(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        """
version: 1
defaults:
  context:
    name: local
contexts:
  - name: local
    engine: c.localhost.rstream.io:9443
    auth:
      token:
        storage:
          value: local-token
""".strip(),
        encoding="utf-8",
    )

    resolved = asyncio.run(
        resolve_client_options(ClientOptions(config_path=str(config), no_token=True))
    )

    assert resolved.token is None
    assert resolved.no_token is True
