from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_candidate_does_not_publish() -> None:
    workflow = read(".github/workflows/release-candidate.yml")
    assert "actions/upload-artifact@" in workflow
    assert "pypa/gh-action-pypi-publish@" not in workflow
    assert "workflow_dispatch:" not in workflow


def test_release_promotion_publishes_github_release_last() -> None:
    workflow = read(".github/workflows/publish.yml")
    assert "environment: pypi" in workflow
    pypi = workflow.index("Verify PyPI release")
    github_release = workflow.index("Publish GitHub release")
    assert github_release > pypi


def test_release_please_creates_tagged_draft() -> None:
    config = json.loads(read("release-please-config.json"))
    package = config["packages"]["."]
    assert package["draft"] is True
    assert package["force-tag-creation"] is True
