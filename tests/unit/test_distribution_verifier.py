from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def metadata(version: str, package_version: str = "1.2.3") -> bytes:
    return (
        f"Metadata-Version: {version}\n"
        "Name: rstreamlabs-rstream\n"
        f"Version: {package_version}\n\n"
    ).encode()


def write_wheel(directory: Path, payload: bytes) -> None:
    path = directory / "rstreamlabs_rstream-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(path, mode="w") as archive:
        archive.writestr("rstreamlabs_rstream-1.2.3.dist-info/METADATA", payload)


def write_sdist(directory: Path, payload: bytes) -> None:
    path = directory / "rstreamlabs_rstream-1.2.3.tar.gz"
    with tarfile.open(path, mode="w:gz") as archive:
        info = tarfile.TarInfo("rstreamlabs_rstream-1.2.3/PKG-INFO")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))


def verify(directory: Path) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).parents[2] / "scripts" / "verify_distribution.py"
    return subprocess.run(
        [sys.executable, str(script), str(directory)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_accepts_matching_metadata_2_6(tmp_path: Path) -> None:
    payload = metadata("2.6")
    write_wheel(tmp_path, payload)
    write_sdist(tmp_path, payload)
    result = verify(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == (
        "verified rstreamlabs-rstream 1.2.3 (metadata 2.6)"
    )


def test_rejects_metadata_with_newer_major_version(tmp_path: Path) -> None:
    payload = metadata("3.0")
    write_wheel(tmp_path, payload)
    write_sdist(tmp_path, payload)
    result = verify(tmp_path)
    assert result.returncode != 0
    assert "unsupported Metadata-Version 3.0" in result.stderr


def test_rejects_wheel_and_sdist_version_mismatch(tmp_path: Path) -> None:
    write_wheel(tmp_path, metadata("2.4"))
    write_sdist(tmp_path, metadata("2.4", package_version="1.2.4"))
    result = verify(tmp_path)
    assert result.returncode != 0
    assert "Name/Version metadata do not match" in result.stderr
