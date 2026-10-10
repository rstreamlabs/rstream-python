from __future__ import annotations

import hashlib
import runpy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / ".github/scripts/verify-pypi-release.py"


def test_publisher_attestations_do_not_change_distribution_digests(
    tmp_path: Path,
) -> None:
    digest = runpy.run_path(str(SCRIPT))["distribution_digests"]
    wheel = "rstreamlabs_rstream-0.7.0-py3-none-any.whl"
    sdist = "rstreamlabs_rstream-0.7.0.tar.gz"
    for name in (wheel, sdist):
        (tmp_path / name).write_bytes(name.encode())
    expected = {
        name: hashlib.sha256(name.encode()).hexdigest() for name in (wheel, sdist)
    }
    assert digest(tmp_path) == expected
    for name in (wheel, sdist):
        (tmp_path / f"{name}.publish.attestation").write_text("{}")
    assert digest(tmp_path) == expected
    (tmp_path / wheel).write_bytes(b"changed")
    assert digest(tmp_path) != expected


@pytest.mark.parametrize("name", ["unknown.txt", "missing.whl.publish.attestation"])
def test_unexpected_or_orphaned_files_are_rejected(tmp_path: Path, name: str) -> None:
    digest = runpy.run_path(str(SCRIPT))["distribution_digests"]
    (tmp_path / "package.whl").write_bytes(b"wheel")
    (tmp_path / name).write_text("{}")
    with pytest.raises(ValueError, match="unexpected distribution files"):
        digest(tmp_path)
