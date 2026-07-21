"""Small HTTP helpers used by the runtime client when project discovery is needed."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote, urljoin

from rstream.config import (
    DEFAULT_API_URL,
    _normalize_control_plane_headers,
    _normalize_region,
    normalize_engine_address,
)
from rstream.errors import ConfigurationError, RuntimeError


@dataclass(frozen=True)
class TokenCredentials:
    """Bearer token credentials for rstream HTTP APIs."""

    token: str


@dataclass(frozen=True)
class TunnelsProjectRegionalEndpoint:
    """Regional engine endpoint authorized for a managed project."""

    provider: str
    region: str
    domain: str
    engine_port: int


@dataclass(frozen=True)
class TunnelsProject:
    """Managed tunnels project metadata required for engine resolution."""

    id: str
    endpoint: str
    url: str | None
    domain: str
    engine_port: int
    placement: str = "regional"
    regional_endpoints: tuple[TunnelsProjectRegionalEndpoint, ...] = ()


class RstreamAPIClient:
    """Minimal Control plane client used by the runtime SDK."""

    def __init__(
        self,
        *,
        api_url: str = DEFAULT_API_URL,
        control_plane_headers: Mapping[str, str] | None = None,
        credentials: TokenCredentials | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.control_plane_headers = dict(
            _normalize_control_plane_headers(control_plane_headers)
        )
        self.credentials = credentials

    async def resolve_tunnels_project(self, endpoint: str) -> TunnelsProject:
        normalized = endpoint.strip()
        if not normalized:
            raise ConfigurationError(
                "Project endpoint is required.",
                code="ERR_RSTREAM_PROJECT_ENDPOINT_REQUIRED",
            )
        data = await self.request_json(
            f"/api/projects/tunnels/resolve/{quote(normalized)}"
        )
        return _project_from_json(data)

    async def request_json(self, path: str) -> Mapping[str, object]:
        try:
            import httpx
        except ImportError as error:
            raise RuntimeError(
                "Install rstream[api] to resolve managed project endpoints.",
                code="ERR_RSTREAM_API_EXTRA_REQUIRED",
            ) from error
        if not path.startswith("/") or path.startswith("//"):
            raise RuntimeError(
                "API request path must be a relative absolute path.",
                code="ERR_RSTREAM_INVALID_API_PATH",
            )
        url = urljoin(f"{self.api_url}/", path.lstrip("/"))
        headers = dict(self.control_plane_headers)
        if self.credentials is not None:
            headers["Authorization"] = f"Bearer {self.credentials.token}"
        async with httpx.AsyncClient(follow_redirects=False, timeout=15) as client:
            response = await client.get(url, headers=headers)
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(
                f"HTTP error {response.status_code}: {response.text}",
                code="ERR_RSTREAM_API_HTTP",
            )
        value = response.json()
        if not isinstance(value, Mapping):
            raise RuntimeError(
                "Control plane returned a non-object JSON response.",
                code="ERR_RSTREAM_API_INVALID_RESPONSE",
            )
        return {str(key): item for key, item in value.items()}


def engine_from_project(project: TunnelsProject, region: str | None = None) -> str:
    requested = _normalize_region(region)
    if requested is not None:
        matches = tuple(
            endpoint
            for endpoint in project.regional_endpoints
            if endpoint.region.strip().lower() == requested
        )
        if not matches:
            available = sorted(
                {
                    endpoint.region.strip().lower()
                    for endpoint in project.regional_endpoints
                    if endpoint.region.strip()
                }
            )
            suffix = f" Available regions: {', '.join(available)}." if available else ""
            raise ConfigurationError(
                f"Region '{requested}' is not available for this project.{suffix}",
                code="ERR_RSTREAM_REGION_UNAVAILABLE",
            )
        if len(matches) > 1:
            raise ConfigurationError(
                f"Region '{requested}' is ambiguous for this project.",
                code="ERR_RSTREAM_REGION_AMBIGUOUS",
            )
        selected = matches[0]
        engine = f"{project.endpoint}.{selected.domain}:{selected.engine_port}"
        normalized = normalize_engine_address(engine)
        if normalized is None:
            raise RuntimeError(
                "Failed to normalize managed project regional engine address.",
                code="ERR_RSTREAM_ENGINE_RESOLUTION",
            )
        return normalized
    if project.endpoint and project.domain:
        engine = f"{project.endpoint}.{project.domain}:{project.engine_port or 443}"
        normalized = normalize_engine_address(engine)
        if normalized is None:
            raise RuntimeError(
                "Failed to normalize managed project engine address.",
                code="ERR_RSTREAM_ENGINE_RESOLUTION",
            )
        return normalized
    if project.url:
        normalized = normalize_engine_address(project.url)
        if normalized is not None:
            return normalized
    raise RuntimeError(
        "Failed to resolve the engine address from the managed tunnels project.",
        code="ERR_RSTREAM_ENGINE_RESOLUTION",
    )


def _project_from_json(data: Mapping[str, object]) -> TunnelsProject:
    project_id = _string_required(data, "id")
    endpoint = _string_required(data, "endpoint")
    domain = _string_required(data, "domain")
    engine_port = _int_required(data, "enginePort")
    placement = data.get("placement")
    url = data.get("url")
    return TunnelsProject(
        id=project_id,
        endpoint=endpoint,
        url=url if isinstance(url, str) else None,
        domain=domain,
        engine_port=engine_port,
        placement=placement if isinstance(placement, str) else "regional",
        regional_endpoints=_regional_endpoints_from_json(data.get("regionalEndpoints")),
    )


def _regional_endpoints_from_json(
    value: object,
) -> tuple[TunnelsProjectRegionalEndpoint, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RuntimeError(
            "Control plane response has invalid 'regionalEndpoints'.",
            code="ERR_RSTREAM_API_INVALID_RESPONSE",
        )
    endpoints: list[TunnelsProjectRegionalEndpoint] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise RuntimeError(
                "Control plane response has invalid 'regionalEndpoints'.",
                code="ERR_RSTREAM_API_INVALID_RESPONSE",
            )
        normalized = {str(key): entry for key, entry in item.items()}
        endpoints.append(
            TunnelsProjectRegionalEndpoint(
                provider=_string_required(normalized, "provider"),
                region=_string_required(normalized, "region"),
                domain=_string_required(normalized, "domain"),
                engine_port=_int_required(normalized, "enginePort"),
            )
        )
    return tuple(endpoints)


def _string_required(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value
    raise RuntimeError(
        f"Control plane response is missing '{key}'.",
        code="ERR_RSTREAM_API_INVALID_RESPONSE",
    )


def _int_required(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, int) and 1 <= value <= 65_535:
        return value
    raise RuntimeError(
        f"Control plane response is missing '{key}'.",
        code="ERR_RSTREAM_API_INVALID_RESPONSE",
    )
