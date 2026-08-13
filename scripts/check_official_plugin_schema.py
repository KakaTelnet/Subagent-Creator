#!/usr/bin/env python3
"""Check the strict Plugin validator against current official manifest docs.

The check downloads the official Markdown page, extracts the fields listed in
its ``Manifest fields`` section, and fails when the documentation introduces a
field that the local strict validator would reject. It requires only Python's
standard library and does not modify the repository.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from validate_plugin import INTERFACE_KEYS, PLUGIN_KEYS


OFFICIAL_SCHEMA_URL = "https://developers.openai.com/plugins/build/plugins.md"
FIELD_PATTERN = re.compile(r"`([A-Za-z][A-Za-z0-9]*)`")


def extract_documented_fields(markdown: str) -> tuple[set[str], set[str]]:
    """Extract top-level and interface field names from official Markdown."""
    start_marker = "### Manifest fields"
    end_marker = "### Path rules"
    start = markdown.find(start_marker)
    end = markdown.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        raise ValueError("official Manifest fields section could not be located")
    section = markdown[start:end]
    interface_marker = "Use the `interface` object"
    split = section.find(interface_marker)
    if split < 0:
        raise ValueError("official interface field subsection could not be located")
    top_level = set(FIELD_PATTERN.findall(section[:split]))
    interface = set(FIELD_PATTERN.findall(section[split:]))
    top_level.discard("plugin")
    interface.discard("interface")
    return top_level, interface


def fetch_official_markdown() -> str:
    """Download the official manifest documentation with a bounded timeout."""
    request = Request(
        OFFICIAL_SCHEMA_URL,
        headers={"User-Agent": "construct-subagent-schema-check/0.1"},
    )
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the optional offline document path used by unit tests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--document",
        type=Path,
        help="Read an official-format Markdown snapshot instead of downloading it",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Return nonzero when official fields exceed the local strict allowlist."""
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        markdown = (
            args.document.read_text(encoding="utf-8")
            if args.document is not None
            else fetch_official_markdown()
        )
        top_level, interface = extract_documented_fields(markdown)
    except (OSError, UnicodeError, ValueError, HTTPError, URLError) as exc:
        print(f"Official Plugin schema check failed: {exc}")
        return 1

    missing_top_level = sorted(top_level - PLUGIN_KEYS)
    missing_interface = sorted(interface - INTERFACE_KEYS)
    if missing_top_level or missing_interface:
        print(
            "Official Plugin schema is newer than the local strict validator: "
            f"top_level={missing_top_level}, interface={missing_interface}"
        )
        return 1

    print(
        "Official Plugin schema compatibility passed: "
        f"{OFFICIAL_SCHEMA_URL} "
        f"(top_level={len(top_level)}, interface={len(interface)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
