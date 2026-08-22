#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TypedDict

PYPI_JSON_URL = "https://pypi.org/pypi/rstreamlabs-rstream/{version}/json"


class PublishedFile(TypedDict):
    digests: dict[str, str]
    filename: str


def distribution_digests(directory: Path) -> dict[str, str]:
    distributions = sorted(
        path
        for path in directory.iterdir()
        if path.name != "SHA256SUMS" and path.is_file()
    )
    if not distributions:
        raise ValueError(f"no distributions found in {directory}")
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in distributions
    }


def published_digests(version: str) -> dict[str, str] | None:
    request = urllib.request.Request(
        PYPI_JSON_URL.format(version=version),
        headers={"User-Agent": "rstream-release-verifier/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    files: list[PublishedFile] = payload["urls"]
    return {item["filename"]: item["digests"]["sha256"] for item in files}


def matches_release(version: str, expected: dict[str, str]) -> bool | None:
    actual = published_digests(version)
    if actual is None:
        return None
    if actual != expected:
        missing = sorted(expected.keys() - actual.keys())
        unexpected = sorted(actual.keys() - expected.keys())
        mismatched = sorted(
            filename
            for filename in expected.keys() & actual.keys()
            if expected[filename] != actual[filename]
        )
        raise ValueError(
            "PyPI release differs from the candidate "
            f"(missing={missing}, unexpected={unexpected}, mismatched={mismatched})"
        )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--github-output", type=Path)
    arguments = parser.parse_args()

    expected = distribution_digests(arguments.directory)
    attempts = 60 if arguments.wait else 1
    for attempt in range(attempts):
        result = matches_release(arguments.version, expected)
        if result:
            if arguments.github_output:
                with arguments.github_output.open("a", encoding="utf-8") as output:
                    output.write("publish=false\n")
            return 0
        if attempt + 1 < attempts:
            time.sleep(10)

    if arguments.wait:
        print(
            f"PyPI release {arguments.version} did not become visible",
            file=sys.stderr,
        )
        return 1
    if arguments.github_output:
        with arguments.github_output.open("a", encoding="utf-8") as output:
            output.write("publish=true\n")
        return 0
    print(f"PyPI release {arguments.version} is not published", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
