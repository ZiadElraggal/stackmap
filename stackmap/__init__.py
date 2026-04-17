"""StackMap — Architecture diagrams that generate themselves from your infrastructure code."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _local_project_version() -> str | None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not pyproject.exists():
        return None
    for line in pyproject.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("version = "):
            return stripped.split("=", 1)[1].strip().strip('"')
    return None

try:
    __version__ = _local_project_version() or version("stackmap")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
