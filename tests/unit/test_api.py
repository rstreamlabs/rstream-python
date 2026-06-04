from __future__ import annotations

import pytest

from rstream.api import (
    RstreamAPIClient,
    TunnelsProject,
    _project_from_json,
    engine_from_project,
)
from rstream.errors import RstreamRuntimeError


def test_engine_from_project_uses_endpoint_domain_and_port() -> None:
    project = TunnelsProject(
        id="project_123",
        endpoint="abc123",
        url=None,
        domain="tunnels.rstream.io",
        engine_port=9443,
    )

    assert engine_from_project(project) == "abc123.tunnels.rstream.io:9443"


def test_engine_from_project_falls_back_to_url() -> None:
    project = TunnelsProject(
        id="project_123",
        endpoint="",
        url="engine.example.test:443",
        domain="",
        engine_port=443,
    )

    assert engine_from_project(project) == "engine.example.test:443"


def test_engine_from_project_rejects_unresolvable_project() -> None:
    project = TunnelsProject(
        id="project_123",
        endpoint="",
        url=None,
        domain="",
        engine_port=443,
    )

    with pytest.raises(RstreamRuntimeError, match="Failed to resolve"):
        engine_from_project(project)


def test_project_from_json_normalizes_control_plane_payload() -> None:
    project = _project_from_json(
        {
            "id": "project_123",
            "endpoint": "abc123",
            "url": "engine.example.test:443",
            "domain": "tunnels.rstream.io",
            "enginePort": 9443,
        }
    )

    assert project.id == "project_123"
    assert project.endpoint == "abc123"
    assert project.url == "engine.example.test:443"
    assert project.domain == "tunnels.rstream.io"
    assert project.engine_port == 9443


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": "", "endpoint": "abc", "domain": "example.test", "enginePort": 443},
        {"id": "project", "endpoint": "", "domain": "example.test", "enginePort": 443},
        {"id": "project", "endpoint": "abc", "domain": "", "enginePort": 443},
        {"id": "project", "endpoint": "abc", "domain": "example.test", "enginePort": 0},
        {
            "id": "project",
            "endpoint": "abc",
            "domain": "example.test",
            "enginePort": 70_000,
        },
    ],
)
def test_project_from_json_rejects_incomplete_payloads(
    payload: dict[str, object],
) -> None:
    with pytest.raises(RstreamRuntimeError, match="Control plane response"):
        _project_from_json(payload)


@pytest.mark.asyncio
async def test_api_client_rejects_absolute_remote_path() -> None:
    client = RstreamAPIClient()

    with pytest.raises(RstreamRuntimeError, match="relative absolute path"):
        await client.request_json("//evil.example.test/project")
