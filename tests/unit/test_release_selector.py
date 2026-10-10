from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / ".github/scripts/select-release-by-tag.py"


def select(pages: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "v0.7.0"],
        input=json.dumps(pages),
        text=True,
        capture_output=True,
        check=False,
    )


def test_draft_on_later_page_is_selected() -> None:
    draft = {"id": 42, "tag_name": "v0.7.0", "draft": True}
    result = select([[{"tag_name": "v0.6.0"}], [draft]])
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == draft


@pytest.mark.parametrize(
    "pages",
    [
        [],
        [[]],
        [[{"tag_name": "v0.6.0"}]],
        [[{"tag_name": "v0.7.0"}], [{"tag_name": "v0.7.0"}]],
        {},
        [{"tag_name": "v0.7.0"}],
        [[None]],
    ],
)
def test_missing_duplicate_or_invalid_release_is_rejected(pages: object) -> None:
    result = select(pages)
    assert result.returncode != 0
    assert result.stdout == ""
