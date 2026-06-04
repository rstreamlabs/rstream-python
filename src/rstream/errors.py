"""Error types exposed by the rstream Python SDK."""

from __future__ import annotations

from collections.abc import Mapping


class RstreamError(Exception):
    """Base class for all SDK errors."""

    code: str
    details: Mapping[str, object] | None

    def __init__(
        self,
        message: str,
        *,
        code: str = "ERR_RSTREAM",
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details) if details is not None else None


class RuntimeError(RstreamError):
    """Raised when the local SDK runtime cannot complete an operation."""


RstreamRuntimeError = RuntimeError


class EngineError(RuntimeError):
    """Raised when the rstream engine returns an error response."""

    engine_code: int

    def __init__(self, engine_code: int, message: str) -> None:
        super().__init__(
            message,
            code="ERR_RSTREAM_ENGINE",
            details={"engine_code": engine_code},
        )
        self.engine_code = engine_code


class ConfigurationError(RuntimeError):
    """Raised when SDK configuration is invalid or incomplete."""


class UnsupportedFeatureError(RuntimeError):
    """Raised when config requests a feature this SDK does not implement."""


class ProtocolError(RuntimeError):
    """Raised when the engine and SDK exchange an invalid protocol frame."""
