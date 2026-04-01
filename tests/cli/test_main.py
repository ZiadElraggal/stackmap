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


def test_scan_repo_with_org_file_builds_org_metadata(tmp_path: Path) -> None:
    repo_root = FIXTURES / "org_repo"
    out = tmp_path / "org-repo.json"

    result = runner.invoke(
        app,
        [
            "scan-repo",
            "--root",
            str(repo_root),
            "--org-file",
            str(repo_root / "org.json"),
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

    payload = json.loads(out.read_text())
    assert payload["metadata"]["organization"]["org_id"] == "o-stackmap"
    assert payload["metadata"]["organization_overlay"]["unscanned_account_ids"] == ["210000000007"]
    assert payload["metadata"]["cross_account_edges"] > 0
    assert any(group["group_type"] == "ou" for group in payload["groups"])
    assert any(group["group_type"] == "account" for group in payload["groups"])


def test_scan_repo_org_strict_rejects_missing_accounts(tmp_path: Path) -> None:
    import json

    repo_root = FIXTURES / "org_repo"
    org_data = json.loads((repo_root / "org.json").read_text())
    org_data["accounts"] = [account for account in org_data["accounts"] if account["id"] != "210000000005"]
    org_override = tmp_path / "org.json"
    org_override.write_text(json.dumps(org_data))

    result = runner.invoke(
        app,
        [
            "scan-repo",
            "--root",
            str(repo_root),
            "--org-file",
            str(org_override),
            "--org-strict",
            "--no-sam-build",
            "--no-terraform-pull-missing",
            "--format",
            "json",
            "--output",
            str(tmp_path / "out.json"),
        ],
    )

    assert result.exit_code == 1
    normalized_output = " ".join(result.output.split())
    assert "missing from the organization file" in normalized_output


def test_org_import_writes_output(monkeypatch, tmp_path: Path) -> None:
    from stackmap.organizations import OrganizationDocument

    def fake_build_org_document_from_aws(profile=None, region=None, root_id=None):  # type: ignore[no-untyped-def]
        assert profile == "sandbox"
        assert region == "us-east-1"
        assert root_id is None
        return OrganizationDocument(
            org_id="o-test",
            root_id="r-root",
            root_name="Root",
            ous=[{"id": "ou-eng", "name": "Engineering", "parent": "r-root", "path": "Root/Engineering"}],
            accounts=[{"id": "210000000001", "name": "prod", "parent": "ou-eng", "ou_path": "Root/Engineering"}],
        )

    monkeypatch.setattr("stackmap.cli.main.build_org_document_from_aws", fake_build_org_document_from_aws)
    out = tmp_path / "org.json"
    result = runner.invoke(
        app,
        [
            "org-import",
            "--profile",
            "sandbox",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert out.exists()

    import json

    payload = json.loads(out.read_text())
    assert payload["org_id"] == "o-test"
    assert payload["accounts"][0]["id"] == "210000000001"


def test_aws_policy_prints_json() -> None:
    result = runner.invoke(app, ["aws-policy", "--service-set", "core"])

    assert result.exit_code == 0
    assert '"Version": "2012-10-17"' in result.output
    assert "ec2:Describe*" in result.output


def test_scan_aws_dry_run_prints_planned_calls(monkeypatch) -> None:
    from stackmap.aws_live.scanner import PlannedAPICall

    class FakeScanner:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            self.kwargs = kwargs

        def startup_summary(self):  # type: ignore[no-untyped-def]
            return {
                "account_id": "123456789012",
                "regions": ["us-east-1"],
                "auth_description": "profile 'sandbox'",
                "org_scan": False,
                "services": ["ec2"],
            }

        def dry_run_plan(self):  # type: ignore[no-untyped-def]
            return [
                PlannedAPICall(
                    account_id="123456789012",
                    region="us-east-1",
                    service="ec2",
                    operation="describe_vpcs",
                    params={},
                )
            ]

    monkeypatch.setattr("stackmap.cli.main.AWSLiveScanner", FakeScanner)

    result = runner.invoke(
        app,
        [
            "scan-aws",
            "--dry-run",
            "--services",
            "ec2",
        ],
    )

    assert result.exit_code == 0
    assert "read-only mode" in result.output.lower()
    assert "describe_vpcs" in result.output
    assert "Planned 1 AWS API calls" in result.output


def test_scan_aws_json_writes_output(monkeypatch, tmp_path: Path) -> None:
    from stackmap.parsers.base import ResourceCategory, StackMapIR, StackMapNode

    class FakeScanner:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            self.kwargs = kwargs

        def startup_summary(self):  # type: ignore[no-untyped-def]
            return {
                "account_id": "123456789012",
                "regions": ["us-east-1"],
                "auth_description": "profile 'sandbox'",
                "org_scan": False,
                "services": ["lambda"],
            }

        def scan(self):  # type: ignore[no-untyped-def]
            return StackMapIR(
                metadata={
                    "source_type": "aws_live",
                    "regions": ["us-east-1"],
                    "selected_services": ["lambda"],
                    "api_calls": 4,
                    "warnings": [],
                    "errors": [],
                },
                nodes=[
                    StackMapNode(
                        id="aws:123456789012:us-east-1:aws_lambda_function:orders-handler",
                        name="orders-handler",
                        resource_type="aws_lambda_function",
                        provider="aws",
                        category=ResourceCategory.SERVERLESS,
                    )
                ],
            )

    monkeypatch.setattr("stackmap.cli.main.AWSLiveScanner", FakeScanner)

    out = tmp_path / "aws-live.json"
    result = runner.invoke(
        app,
        [
            "scan-aws",
            "--services",
            "lambda",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert out.exists()

    import json

    payload = json.loads(out.read_text())
    assert payload["metadata"]["source_type"] == "aws_live"
    assert payload["nodes"][0]["resource_type"] == "aws_lambda_function"


def test_scan_aws_serve_uses_serve_command(monkeypatch, tmp_path: Path) -> None:
    from stackmap.parsers.base import StackMapIR

    called: dict[str, object] = {}

    class FakeScanner:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            self.kwargs = kwargs

        def startup_summary(self):  # type: ignore[no-untyped-def]
            return {
                "account_id": "123456789012",
                "regions": ["us-east-1"],
                "auth_description": "profile 'sandbox'",
                "org_scan": False,
                "services": ["ec2"],
            }

        def scan(self):  # type: ignore[no-untyped-def]
            return StackMapIR(metadata={"source_type": "aws_live", "warnings": [], "errors": []})

    def fake_serve(**kwargs):  # type: ignore[no-untyped-def]
        called.update(kwargs)

    monkeypatch.setattr("stackmap.cli.main.AWSLiveScanner", FakeScanner)
    monkeypatch.setattr("stackmap.cli.main.serve", fake_serve)

    out = tmp_path / "aws-live.json"
    result = runner.invoke(
        app,
        [
            "scan-aws",
            "--services",
            "ec2",
            "--output",
            str(out),
            "--serve",
        ],
    )

    assert result.exit_code == 0
    assert called["source"] == str(out)
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 3000
    assert called["watch"] is False
    assert called["watch_interval"] == 1.0


def test_scan_aws_org_scan_requires_org_file() -> None:
    result = runner.invoke(app, ["scan-aws", "--org-scan"])

    assert result.exit_code == 1
    assert "--org-scan requires --org-file" in result.output
