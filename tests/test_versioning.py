from pathlib import Path

from stackmap import __version__


def test_dunder_version_matches_project_metadata() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    version_line = next(
        line.strip() for line in pyproject.read_text().splitlines() if line.strip().startswith("version = ")
    )
    project_version = version_line.split("=", 1)[1].strip().strip('"')
    assert __version__ == project_version
