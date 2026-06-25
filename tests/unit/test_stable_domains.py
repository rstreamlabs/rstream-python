from __future__ import annotations

import re

import pytest

from rstream.stable_domains import engine_hostname, generate_stable_domain

_GENERATED = re.compile(r"^r[0-9a-f]{8}-project-42\.t\.edge\.example\.com$")


def test_generate_stable_domain_for_managed_engine() -> None:
    got = generate_stable_domain("https://Project-42.edge.example.com:443")
    assert got is not None
    assert _GENERATED.match(got), got


# Same rejection set as the Go reference SDK (stable_domains_test.go), so the
# two implementations agree on which engines are not project-scoped hosts.
@pytest.mark.parametrize(
    "engine",
    [
        "",
        "localhost:443",
        "bad_label.example.com:443",
        "project.bad_cluster.example.com:443",
        "[2001:db8::1]:443",
    ],
)
def test_generate_stable_domain_rejects_unsupported_engines(engine: str) -> None:
    assert generate_stable_domain(engine) is None


def test_generated_slug_differs_between_calls() -> None:
    first = generate_stable_domain("project.edge.example.com:443")
    second = generate_stable_domain("project.edge.example.com:443")
    assert first is not None and second is not None
    # The slug is random per call; the caller is responsible for generating
    # once and reusing, which is what makes the address stable.
    assert first != second


def test_generated_hostname_fits_dns_label_limit() -> None:
    long_endpoint = "a" * 54  # leaves only 8 chars for "<slug>-"
    assert generate_stable_domain(f"{long_endpoint}.edge.example.com:443") is None
    endpoint = "a" * 53  # leaves exactly 9 chars, the slug length
    got = generate_stable_domain(f"{endpoint}.edge.example.com:443")
    assert got is not None
    first_label = got.split(".", 1)[0]
    assert len(first_label) <= 63


@pytest.mark.parametrize(
    ("engine", "expected"),
    [
        ("https://Host.Example.com:443", "host.example.com"),
        ("host.example.com.", "host.example.com"),
        ("[2001:db8::1]:443", ""),
        ("192.0.2.10:443", "192.0.2.10"),
        ("", ""),
    ],
)
def test_engine_hostname_normalization(engine: str, expected: str) -> None:
    assert engine_hostname(engine) == expected
