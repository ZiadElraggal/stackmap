"""StackMap — Architecture diagrams that generate themselves from your infrastructure code."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("stackmap")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
