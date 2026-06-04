"""Package version metadata."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rstreamlabs-rstream")
except PackageNotFoundError:
    __version__ = "unknown"
