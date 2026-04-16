"""AWS profile discovery helpers for the local viewer."""

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


def _profile_name(section: str) -> str | None:
    if section == "default":
        return "default"
    if section.startswith("profile "):
        return section.removeprefix("profile ").strip() or None
    return section.strip() or None


def discover_aws_profiles(home: Path | None = None) -> list[str]:
    """Return AWS profile names from ~/.aws/config and ~/.aws/credentials."""
    root = home or Path.home()
    names: set[str] = set()
    for path in [root / ".aws" / "config", root / ".aws" / "credentials"]:
        if not path.exists():
            continue
        parser = ConfigParser()
        parser.read(path)
        for section in parser.sections():
            name = _profile_name(section)
            if name:
                names.add(name)
    return sorted(names, key=lambda item: (item != "default", item))
