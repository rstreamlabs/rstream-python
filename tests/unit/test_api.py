from __future__ import annotations

import httpx
import pytest

from rstream.api import (
    RstreamAPIClient,
    TunnelsProject,
    TunnelsProjectRegionalEndpoint,
    _project_from_json,
    engine_from_project,
)
from rstream.errors import ConfigurationError, RstreamRuntimeError


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


def test_engine_from_project_selects_only_authorized_regions() -> None:
    project = TunnelsProject(
        id="project_123",
        endpoint="abc123",
        url="abc123.global.example.test:443",
        domain="global.example.test",
        engine_port=443,
        placement="global",
        regional_endpoints=(
            TunnelsProjectRegionalEndpoint(
                provider="aws",
                region="eu-west-3",
                domain="eu.example.test",
                engine_port=8443,
            ),
            TunnelsProjectRegionalEndpoint(
                provider="aws",
                region="us-east-1",
                domain="us.example.test",
                engine_port=443,
            ),
        ),
    )

    assert engine_from_project(project, "US-EAST-1") == "abc123.us.example.test:443"
    with pytest.raises(ConfigurationError, match="Available regions"):
        engine_from_project(project, "ap-southeast-1")


def test_engine_from_project_rejects_ambiguous_regions() -> None:
    endpoint = TunnelsProjectRegionalEndpoint(
        provider="aws",
        region="eu-west-3",
        domain="eu.example.test",
        engine_port=443,
    )
    project = TunnelsProject(
        id="project_123",
        endpoint="abc123",
        url=None,
        domain="global.example.test",
        engine_port=443,
        regional_endpoints=(endpoint, endpoint),
    )

    with pytest.raises(ConfigurationError, match="ambiguous"):
        engine_from_project(project, "eu-west-3")


def test_project_from_json_normalizes_control_plane_payload() -> None:
    project = _project_from_json(
        {
            "id": "project_123",
            "endpoint": "abc123",
            "url": "engine.example.test:443",
            "domain": "tunnels.rstream.io",
            "enginePort": 9443,
            "placement": "global",
            "regionalEndpoints": [
                {
                    "provider": "aws",
                    "region": "eu-west-3",
                    "domain": "eu.example.test",
                    "enginePort": 8443,
                }
            ],
        }
    )

    assert project.id == "project_123"
    assert project.endpoint == "abc123"
    assert project.url == "engine.example.test:443"
    assert project.domain == "tunnels.rstream.io"
    assert project.engine_port == 9443
    assert project.placement == "global"
    assert project.regional_endpoints[0].region == "eu-west-3"


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


@pytest.mark.asyncio
async def test_api_client_sends_control_plane_headers_without_following_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, *, follow_redirects: bool, timeout: int) -> None:
            observed["follow_redirects"] = follow_redirects
            observed["timeout"] = timeout

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(
            self,
            exc_type: object,
            exc_value: object,
            traceback: object,
        ) -> None:
            return None

        async def get(
            self,
            url: str,
            *,
            headers: dict[str, str],
        ) -> httpx.Response:
            observed["url"] = url
            observed["headers"] = headers
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    client = RstreamAPIClient(
        control_plane_headers={"x-vercel-protection-bypass": "test-secret"}
    )

    assert await client.request_json("/api/test") == {"ok": True}
    assert observed == {
        "follow_redirects": False,
        "headers": {"X-Vercel-Protection-Bypass": "test-secret"},
        "timeout": 15,
        "url": "https://rstream.io/api/test",
    }


def test_api_client_rejects_reserved_control_plane_headers() -> None:
    with pytest.raises(ConfigurationError, match="reserved"):
        RstreamAPIClient(control_plane_headers={"Authorization": "secret"})
