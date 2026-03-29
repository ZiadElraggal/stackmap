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
