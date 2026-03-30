#!/usr/bin/env python3
"""Render a stable Homebrew formula for a tagged StackMap release."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_formula(version: str, tag: str, sha256: str, repository: str) -> str:
    return f"""class Stackmap < Formula
  desc "Architecture diagrams that generate themselves from infrastructure code"
  homepage "https://github.com/{repository}"
  url "https://github.com/{repository}/archive/refs/tags/{tag}.tar.gz"
  version "{version}"
  sha256 "{sha256}"
  license "MIT"

  depends_on "python@3.12"

  def install
    python = Formula["python@3.12"].opt_bin/"python3.12"
    system python, "-m", "venv", libexec
    system libexec/"bin/pip", "install", "--upgrade", "pip"
    system libexec/"bin/pip", "install", buildpath
    bin.install_symlink libexec/"bin/stackmap"
  end

  test do
    output = shell_output("#{{bin}}/stackmap version")
    assert_match "stackmap", output
  end
end
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="Release version without v prefix (e.g. 0.2.0)")
    parser.add_argument("--tag", required=True, help="Release tag exactly as published (e.g. v0.2.0 or 0.2.0)")
    parser.add_argument("--sha256", required=True, help="SHA256 of <tag>.tar.gz release archive")
    parser.add_argument("--repository", required=True, help="GitHub repo slug, e.g. owner/repo")
    parser.add_argument("--output", required=True, help="Output path for formula")
    args = parser.parse_args()

    formula = build_formula(args.version, args.tag, args.sha256, args.repository)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(formula)


if __name__ == "__main__":
    main()
