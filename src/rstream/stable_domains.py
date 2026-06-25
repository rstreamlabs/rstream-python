# See LICENSE file in the project root for license information.

"""Stable domain generation for published tunnels.

A published tunnel without a requested hostname is given a fresh engine
endpoint on every creation, so an address that survives a restart has to be
requested explicitly. This module derives a stable, project-scoped hostname
from the engine address the same way the Go and C++ SDKs do, so an application
can generate one once at startup and reuse it on every reconnect.

The shape is ``<slug>-<project-endpoint>.t.<cluster-domain>``, where the slug
is a random ``r`` followed by eight hex characters. Generating the slug once
and keeping it for the process lifetime is what makes the address stable; the
helper is intentionally pure so the caller owns that lifecycle.
"""

from __future__ import annotations

import re
import secrets
from urllib.parse import urlsplit

_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def engine_hostname(engine: str) -> str:
    """Reduce an engine address to a bare lowercase hostname.

    Strips an optional scheme, port, and IPv6 brackets. Returns an empty
    string for inputs that are not a plain DNS hostname (an IP literal, a
    value that still contains a colon), which the generator treats as
    unsupported.
    """
    value = engine.strip()
    if not value:
        return ""
    if "://" in value:
        value = urlsplit(value).netloc or value
    # Strip a trailing :port without disturbing an IPv6 literal in brackets.
    if value.startswith("["):
        host, _, _ = value.partition("]")
        value = host.lstrip("[")
    else:
        host, sep, port = value.rpartition(":")
        if sep and port.isdigit():
            value = host
    value = value.strip("[]").strip().rstrip(".").lower()
    if ":" in value:
        return ""
    return value


def generate_stable_domain(engine: str) -> str | None:
    """Derive a stable project-scoped hostname from the engine address.

    Returns ``None`` when the engine is not a managed, project-scoped host
    (self-signed clusters, IP literals, single-label hosts), so the caller
    falls back to an engine-allocated address.
    """
    host = engine_hostname(engine)
    if not host:
        return None
    labels = host.split(".")
    if len(labels) < 2:
        return None
    project_endpoint = labels[0]
    cluster_domain = ".".join(labels[1:])
    if not _LABEL_RE.match(project_endpoint) or not _valid_cluster_domain(
        cluster_domain
    ):
        return None
    # A DNS label caps at 63 characters; reserve room for "<slug>-<endpoint>".
    max_slug_len = 63 - len(project_endpoint) - 1
    if max_slug_len < 9:
        return None
    slug = _random_slug()[:max_slug_len]
    return f"{slug}-{project_endpoint}.t.{cluster_domain}"


def _valid_cluster_domain(domain: str) -> bool:
    return all(_LABEL_RE.match(label) for label in domain.split("."))


def _random_slug() -> str:
    return "r" + secrets.token_hex(4)
