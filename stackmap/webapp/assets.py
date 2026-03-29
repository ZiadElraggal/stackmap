"""Resolve packaged and development frontend assets."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def get_packaged_public_dir() -> Path | None:
    """Return packaged static dir when available."""
    try:
        candidate = resources.files("stackmap.webapp").joinpath("static")
    except (ModuleNotFoundError, FileNotFoundError):
        return None

    path = Path(str(candidate))
    if (path / "index.html").exists():
        return path
    return None


def get_dev_frontend_dir() -> Path | None:
    """Return repo frontend dir for editable/dev workflows."""
    root = Path(__file__).resolve().parents[2]
    candidate = root / "frontend"
    if candidate.exists():
        return candidate
    return None


def get_dev_frontend_public_dir() -> Path | None:
    """Return dev Nuxt static output dir when present."""
    frontend = get_dev_frontend_dir()
    if frontend is None:
        return None

    candidates = [
        frontend / ".output" / "public",
        frontend / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate
    return None


def get_preferred_public_dir() -> Path | None:
    """Prefer packaged assets, then dev assets."""
    return get_packaged_public_dir() or get_dev_frontend_public_dir()
