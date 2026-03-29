from pathlib import Path

import pytest

pytest.importorskip("typer")
typer_testing = pytest.importorskip("typer.testing")
CliRunner = typer_testing.CliRunner
from stackmap.cli.main import app  # noqa: E402

FIXTURES = Path(__file__).parent.parent / "fixtures"
runner = CliRunner()


def test_scan_json_writes_output(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    result = runner.invoke(
        app,
        [
            "scan",
            "--source",
            str(FIXTURES / "simple-lambda-api.tfstate"),
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert out.exists()


def test_scan_html_uses_exporter(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "out.html"
    called = {"value": False}

    def fake_export(ir, output_path):  # type: ignore[no-untyped-def]
        called["value"] = True
        Path(output_path).write_text("<html>ok</html>")

    monkeypatch.setattr("stackmap.export.export_ir_to_html", fake_export)

    result = runner.invoke(
        app,
        [
            "scan",
            "--source",
            str(FIXTURES / "simple-lambda-api.tfstate"),
            "--format",
            "html",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert called["value"] is True
    assert out.exists()


def test_scan_cloudformation_json_writes_output(tmp_path: Path) -> None:
    out = tmp_path / "out-cfn.json"
    result = runner.invoke(
        app,
        [
            "scan",
            "--source",
            str(FIXTURES / "cloudformation-simple.json"),
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert out.exists()


def test_scan_sam_writes_output(tmp_path: Path) -> None:
    out = tmp_path / "out-sam.json"
    result = runner.invoke(
        app,
        [
            "scan",
            "--source",
            str(FIXTURES / "sam-simple.json"),
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert out.exists()
    assert "Source type" in result.output
    assert "sam" in result.output.lower()


def test_scan_invalid_format_fails_fast(tmp_path: Path) -> None:
    out = tmp_path / "out.invalid"
    result = runner.invoke(
        app,
        [
            "scan",
            "--source",
            str(FIXTURES / "simple-lambda-api.tfstate"),
            "--format",
            "yaml",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 1
    assert "Format 'yaml' not supported" in result.output


def test_scan_parse_error_is_clean(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "out.json"

    def fake_parse(_source: str):  # type: ignore[no-untyped-def]
        raise ValueError("YAML CloudFormation template detected but PyYAML is not installed.")

    monkeypatch.setattr("stackmap.cli.main._parse_source", fake_parse)
    result = runner.invoke(
        app,
        [
            "scan",
            "--source",
            str(FIXTURES / "cloudformation-simple.json"),
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 1
    assert "PyYAML is not installed" in result.output
