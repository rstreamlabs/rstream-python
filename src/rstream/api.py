"""Small HTTP helpers used by the runtime client when project discovery is needed."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote, urljoin

from rstream.config import DEFAULT_API_URL, normalize_engine_address
from rstream.errors import ConfigurationError, RuntimeError


@dataclass(frozen=True)
class TokenCredentials:
    """Bearer token credentials for rstream HTTP APIs."""

    token: str


@dataclass(frozen=True)
class TunnelsProject:
    """Managed tunnels project metadata required for engine resolution."""

    id: str
    endpoint: str
    url: str | None
    domain: str
    engine_port: int


class RstreamAPIClient:
    """Minimal Control plane client used by the runtime SDK."""

    def __init__(
        self,
        *,
        api_url: str = DEFAULT_API_URL,
        credentials: TokenCredentials | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
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
        headers: dict[str, str] = {}
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


def engine_from_project(project: TunnelsProject) -> str:
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
    url = data.get("url")
    return TunnelsProject(
        id=project_id,
        endpoint=endpoint,
        url=url if isinstance(url, str) else None,
        domain=domain,
        engine_port=engine_port,
    )


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
