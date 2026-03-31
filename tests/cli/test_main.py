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


def test_scan_repo_json_merges_multiple_source_types(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "simple.tfstate").write_text((FIXTURES / "simple-lambda-api.tfstate").read_text())
    (repo_root / "cfn.json").write_text((FIXTURES / "cloudformation-simple.json").read_text())
    (repo_root / "sam.json").write_text((FIXTURES / "sam-simple.json").read_text())

    out = tmp_path / "repo-out.json"
    result = runner.invoke(
        app,
        [
            "scan-repo",
            "--root",
            str(repo_root),
            "--no-sam-build",
            "--no-terraform-pull-missing",
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert out.exists()

    import json

    data = json.loads(out.read_text())
    assert data["metadata"]["source_type"] == "repo"
    discovered = data["metadata"]["discovered_sources"]
    discovered_types = {entry["type"] for entry in discovered}
    assert {"terraform", "cloudformation", "sam"}.issubset(discovered_types)
    assert len(data["nodes"]) > 0


def test_scan_repo_include_filter_excludes_other_types(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "simple.tfstate").write_text((FIXTURES / "simple-lambda-api.tfstate").read_text())
    (repo_root / "cfn.json").write_text((FIXTURES / "cloudformation-simple.json").read_text())

    out = tmp_path / "repo-out-filtered.json"
    result = runner.invoke(
        app,
        [
            "scan-repo",
            "--root",
            str(repo_root),
            "--include",
            "cloudformation",
            "--no-sam-build",
            "--no-terraform-pull-missing",
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0

    import json

    data = json.loads(out.read_text())
    discovered = data["metadata"]["discovered_sources"]
    discovered_types = {entry["type"] for entry in discovered}
    assert discovered_types == {"cloudformation"}


def test_scan_repo_does_not_classify_non_template_yaml_as_cloudformation(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "cfn.yaml").write_text(
        "\n".join(
            [
                "AWSTemplateFormatVersion: '2010-09-09'",
                "Resources:",
                "  Bucket:",
                "    Type: AWS::S3::Bucket",
            ]
        )
    )
    (repo_root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\npackages: {}\n")

    out = tmp_path / "repo-out-yaml-filter.json"
    result = runner.invoke(
        app,
        [
            "scan-repo",
            "--root",
            str(repo_root),
            "--include",
            "cloudformation",
            "--no-sam-build",
            "--no-terraform-pull-missing",
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0

    import json

    data = json.loads(out.read_text())
    discovered_paths = {Path(entry["path"]).name for entry in data["metadata"]["discovered_sources"]}
    assert discovered_paths == {"cfn.yaml"}


def test_scan_repo_ignores_claude_worktrees(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "cfn.json").write_text((FIXTURES / "cloudformation-simple.json").read_text())
    worktree_dir = repo_root / ".claude" / "worktrees" / "w1"
    worktree_dir.mkdir(parents=True)
    (worktree_dir / "cfn.json").write_text((FIXTURES / "cloudformation-simple.json").read_text())

    out = tmp_path / "repo-out-ignore-worktrees.json"
    result = runner.invoke(
        app,
        [
            "scan-repo",
            "--root",
            str(repo_root),
            "--include",
            "cloudformation",
            "--no-sam-build",
            "--no-terraform-pull-missing",
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0

    import json

    data = json.loads(out.read_text())
    discovered_paths = [entry["path"] for entry in data["metadata"]["discovered_sources"]]
    assert len(discovered_paths) == 1
    assert discovered_paths[0].endswith("/cfn.json")
    assert "/.claude/" not in discovered_paths[0]


def test_scan_repo_invalid_include_type_fails(tmp_path: Path) -> None:
    out = tmp_path / "repo-out.json"
    result = runner.invoke(
        app,
        [
            "scan-repo",
            "--root",
            str(tmp_path),
            "--include",
            "kubernetes",
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 1
    assert "Unsupported include type(s)" in result.output


def test_scan_accepts_stackmap_ir_json(tmp_path: Path) -> None:
    import json

    stackmap_ir = {
        "metadata": {"source_type": "repo"},
        "nodes": [],
        "edges": [],
        "groups": [],
    }
    source = tmp_path / "stackmap-ir.json"
    source.write_text(json.dumps(stackmap_ir))

    out = tmp_path / "reserialized.json"
    result = runner.invoke(
        app,
        [
            "scan",
            "--source",
            str(source),
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert out.exists()
    assert "Source type" in result.output
    assert "repo" in result.output.lower()


def test_diff_json_writes_output(tmp_path: Path) -> None:
    out = tmp_path / "diff.json"
    result = runner.invoke(
        app,
        [
            "diff",
            "--from",
            str(FIXTURES / "timeline-before.json"),
            "--to",
            str(FIXTURES / "timeline-after.json"),
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert out.exists()

    import json

    payload = json.loads(out.read_text())
    assert payload["summary"] == {
        "added": 2,
        "removed": 1,
        "modified": 1,
        "unchanged": 4,
    }


def test_diff_html_uses_exporter(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "diff.html"
    called = {"value": False}

    def fake_export(ir, output_path):  # type: ignore[no-untyped-def]
        called["value"] = True
        assert ir.metadata["diff_mode"] is True
        Path(output_path).write_text("<html>diff</html>")

    monkeypatch.setattr("stackmap.export.export_ir_to_html", fake_export)

    result = runner.invoke(
        app,
        [
            "diff",
            "--from",
            str(FIXTURES / "timeline-before.json"),
            "--to",
            str(FIXTURES / "timeline-after.json"),
            "--format",
            "html",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert called["value"] is True
    assert out.exists()


def test_scan_accepts_stackmap_diff_json(tmp_path: Path) -> None:
    diff_out = tmp_path / "timeline-demo.json"
    diff_result = runner.invoke(
        app,
        [
            "diff",
            "--from",
            str(FIXTURES / "timeline-before.json"),
            "--to",
            str(FIXTURES / "timeline-after.json"),
            "--format",
            "json",
            "--output",
            str(diff_out),
        ],
    )
    assert diff_result.exit_code == 0

    roundtrip_out = tmp_path / "served-like.json"
    scan_result = runner.invoke(
        app,
        [
            "scan",
            "--source",
            str(diff_out),
            "--format",
            "json",
            "--output",
            str(roundtrip_out),
        ],
    )

    assert scan_result.exit_code == 0
    assert roundtrip_out.exists()
    assert "repo" not in scan_result.output.lower()
