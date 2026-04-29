from __future__ import annotations

import os
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
    """Return the frontend bundle to serve.

    By default prefer the packaged bundle shipped with the installed package —
    that's what end users see. Developers can opt into the in-repo dev bundle
    at ``frontend/.output/public`` by setting ``STACKMAP_DEV_FRONTEND=1``.

    Historically we preferred the dev bundle over the packaged one. That
    silently masked stale-packaged-bundle bugs (e.g. billing UI visible
    locally but missing on published builds), so the default is now reversed.
    """
    if os.environ.get("STACKMAP_DEV_FRONTEND") == "1":
        dev_public = get_dev_frontend_public_dir()
        if dev_public:
            return dev_public
    packaged = get_packaged_public_dir()
    if packaged:
        return packaged
    # Fall back to dev bundle if no packaged bundle is present (e.g. running
    # directly out of a freshly-cloned repo without a wheel build).
    return get_dev_frontend_public_dir()
