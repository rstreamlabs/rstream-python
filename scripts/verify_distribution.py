#!/usr/bin/env python3

"""Validate release archives before handing them to a package registry."""

from __future__ import annotations

import argparse
import email.policy
import re
import tarfile
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path

MAX_METADATA_BYTES = 1024 * 1024
MAX_METADATA_VERSION = (2, 6)
METADATA_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)$")


@dataclass(frozen=True)
class DistributionMetadata:
    name: str
    version: str
    metadata_version: tuple[int, int]


def parse_metadata(payload: bytes, source: str) -> DistributionMetadata:
    if len(payload) > MAX_METADATA_BYTES:
        raise ValueError(f"{source} metadata exceeds the 1 MiB limit")
    document = BytesParser(policy=email.policy.compat32).parsebytes(payload)
    raw_metadata_version = document.get("Metadata-Version", "")
    match = METADATA_VERSION_PATTERN.fullmatch(raw_metadata_version)
    if match is None:
        raise ValueError(f"{source} has an invalid Metadata-Version")
    metadata_version = (int(match.group(1)), int(match.group(2)))
    if metadata_version > MAX_METADATA_VERSION:
        maximum = ".".join(str(part) for part in MAX_METADATA_VERSION)
        raise ValueError(
            f"{source} uses unsupported Metadata-Version "
            f"{raw_metadata_version}; maximum is {maximum}"
        )
    name = document.get("Name", "").strip()
    version = document.get("Version", "").strip()
    if not name or not version:
        raise ValueError(f"{source} metadata must contain Name and Version")
    return DistributionMetadata(name, version, metadata_version)


def read_wheel_metadata(path: Path) -> DistributionMetadata:
    with zipfile.ZipFile(path) as archive:
        candidates = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(candidates) != 1:
            raise ValueError(f"{path.name} must contain exactly one METADATA file")
        info = archive.getinfo(candidates[0])
        if info.file_size > MAX_METADATA_BYTES:
            raise ValueError(f"{path.name} metadata exceeds the 1 MiB limit")
        return parse_metadata(archive.read(info), path.name)


def read_sdist_metadata(path: Path) -> DistributionMetadata:
    with tarfile.open(path, mode="r:gz") as archive:
        candidates = [
            member
            for member in archive.getmembers()
            if member.isfile() and member.name.endswith("/PKG-INFO")
        ]
        if len(candidates) != 1:
            raise ValueError(f"{path.name} must contain exactly one PKG-INFO file")
        member = candidates[0]
        if member.size > MAX_METADATA_BYTES:
            raise ValueError(f"{path.name} metadata exceeds the 1 MiB limit")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise ValueError(f"{path.name} PKG-INFO could not be read")
        return parse_metadata(extracted.read(MAX_METADATA_BYTES + 1), path.name)


def verify_distribution(directory: Path) -> DistributionMetadata:
    wheels = sorted(directory.glob("*.whl"))
    sdists = sorted(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("distribution directory must contain one wheel and one sdist")
    wheel_metadata = read_wheel_metadata(wheels[0])
    sdist_metadata = read_sdist_metadata(sdists[0])
    if (wheel_metadata.name, wheel_metadata.version) != (
        sdist_metadata.name,
        sdist_metadata.version,
    ):
        raise ValueError("wheel and sdist Name/Version metadata do not match")
    return wheel_metadata


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    return parser.parse_args()


def main() -> None:
    metadata = verify_distribution(arguments().directory)
    metadata_version = ".".join(str(part) for part in metadata.metadata_version)
    print(f"verified {metadata.name} {metadata.version} (metadata {metadata_version})")


if __name__ == "__main__":
    main()
