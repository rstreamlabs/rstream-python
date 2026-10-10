"""Anonymous, bounded Engine API discovery cached by each runtime client."""

from __future__ import annotations

import asyncio
import json
import re
import ssl
import time
from contextlib import suppress
from urllib.parse import urlsplit

from rstream.config import TLSOptions
from rstream.errors import RuntimeError


def has_client_certificate(tls: TLSOptions | None) -> bool:
    return tls is not None and bool(tls.cert_file or tls.certificate)


def _invalid() -> RuntimeError:
    return RuntimeError(
        "Engine returned invalid or unavailable mTLS API discovery.",
        code="ERR_RSTREAM_ENGINE_DISCOVERY",
    )


def _target(value: object, engine: str) -> str:
    if not isinstance(value, dict):
        raise _invalid()
    project = urlsplit("https://" + engine).hostname
    project = project.split(".")[0] if project else None
    api_url = value.get("mtlsApiUrl")
    capabilities = value.get("capabilities")
    if (
        type(value.get("version")) is not int
        or value.get("version") != 1
        or value.get("projectEndpoint") != project
        or not isinstance(api_url, str)
        or not isinstance(capabilities, list)
        or not all(isinstance(item, str) for item in capabilities)
        or "engine-api-mtls" not in capabilities
    ):
        raise _invalid()
    try:
        parsed = urlsplit(api_url)
        if (
            parsed.scheme != "https"
            or parsed.path != "/api"
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
            or not parsed.hostname
            or parsed.hostname.split(".")[0] != project
            or (parsed.port is not None and parsed.port == 0)
            or re.search(r"[\s\\%]", parsed.netloc)
        ):
            raise _invalid()
        return parsed.netloc
    except ValueError as error:
        raise _invalid() from error


class EngineAPIDiscovery:
    def __init__(self) -> None:
        self._cache: tuple[str, str, float] | None = None
        self._pending: asyncio.Task[str] | None = None
        self._closed = False

    async def resolve(self, engine: str, tls: TLSOptions | None) -> str:
        if self._closed:
            raise RuntimeError(
                "rstream client is closed.", code="ERR_RSTREAM_CLIENT_CLOSED"
            )
        if (
            self._cache
            and self._cache[0] == engine
            and self._cache[2] > time.monotonic()
        ):
            return self._cache[1]
        if self._pending is None:
            self._pending = asyncio.create_task(self._discover(engine, tls))
            self._pending.add_done_callback(self._finished)
        return await asyncio.shield(self._pending)

    def _finished(self, task: asyncio.Task[str]) -> None:
        if self._pending is task:
            self._pending = None
        if not task.cancelled():
            task.exception()

    def invalidate(self) -> None:
        self._cache = None

    async def close(self) -> None:
        self._closed = True
        self._cache = None
        pending = self._pending
        if pending is not None:
            pending.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await pending

    async def _discover(self, engine: str, tls: TLSOptions | None) -> str:
        return await asyncio.wait_for(self._request(engine, tls), timeout=5)

    async def _request(self, engine: str, tls: TLSOptions | None) -> str:
        try:
            import httpx
        except ImportError as error:
            raise RuntimeError(
                "Install rstream[api] to call the engine API.",
                code="ERR_RSTREAM_API_EXTRA_REQUIRED",
            ) from error
        trust = ssl.create_default_context(cafile=tls.ca_file if tls else None)
        async with (
            httpx.AsyncClient(
                verify=trust, timeout=5, follow_redirects=False, trust_env=False
            ) as client,
            client.stream(
                "GET", f"https://{engine}/.well-known/rstream/engine"
            ) as response,
        ):
            if response.status_code != 200:
                raise _invalid()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 16_384:
                    raise _invalid()
            try:
                value: object = json.loads(body)
            except (ValueError, UnicodeError) as error:
                raise _invalid() from error
            target = _target(value, engine)
            cache_control = response.headers.get("Cache-Control", "").lower()
            age = response.headers.get("Age", "0")
            max_age = re.search(r"(?:^|,)\s*max-age=(\d+)(?:\s*,|$)", cache_control)
            ttl = min(int(max_age[1]), 86_400) if max_age else 3_600
            ttl = max(0, ttl - int(age)) if age.isdigit() else 0
            if "no-store" in cache_control or "no-cache" in cache_control:
                ttl = 0
            if not self._closed:
                self._cache = (engine, target, time.monotonic() + ttl)
            return target
