"""Select exactly one release from paginated GitHub API output, including drafts."""

from __future__ import annotations

import argparse
import json
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    args = parser.parse_args()
    pages = json.load(sys.stdin)
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        parser.error("expected paginated release arrays")
    releases = [release for page in pages for release in page]
    if not all(isinstance(release, dict) for release in releases):
        parser.error("expected release objects")
    matches = [release for release in releases if release.get("tag_name") == args.tag]
    if len(matches) != 1:
        parser.error(f"expected exactly one release for tag {args.tag}")
    json.dump(matches[0], sys.stdout)


if __name__ == "__main__":
    main()
