"""Sync Nuxt static output into the Python package asset directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def sync_assets(source: Path, dest: Path, clean: bool = False) -> None:
    if not source.exists() or not (source / "index.html").exists():
        raise RuntimeError(
            f"Nuxt static output not found at {source}. "
            "Run `cd frontend && npm run generate` first."
        )

    if clean and dest.exists():
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("frontend/.output/public"),
        help="Nuxt static output directory (default: frontend/.output/public)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("stackmap/webapp/static"),
        help="Destination package asset directory (default: stackmap/webapp/static)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove destination directory before syncing",
    )
    args = parser.parse_args()

    sync_assets(args.source.resolve(), args.dest.resolve(), clean=args.clean)
    print(f"Synced frontend assets: {args.source} -> {args.dest}")


if __name__ == "__main__":
    main()
