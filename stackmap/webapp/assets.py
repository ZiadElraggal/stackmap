from __future__ import annotations

from pathlib import Path


def get_packaged_public_dir() -> Path | None:
    candidate = Path(__file__).resolve().parent / "static"
    if (candidate / "index.html").exists():
        return candidate
    return None


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_dev_frontend_dir() -> Path | None:
    candidate = get_repo_root() / "frontend"
    if candidate.exists():
        return candidate
    return None


def get_dev_frontend_public_dir() -> Path | None:
    frontend_dir = get_dev_frontend_dir()
    if not frontend_dir:
        return None
    candidate = frontend_dir / ".output" / "public"
    if (candidate / "index.html").exists():
        return candidate
    return None


def get_preferred_public_dir() -> Path | None:
    dev_public = get_dev_frontend_public_dir()
    if dev_public:
        return dev_public
    return get_packaged_public_dir()
