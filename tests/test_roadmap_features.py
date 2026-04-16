from pathlib import Path

from stackmap.aws_live.profiles import discover_aws_profiles
from stackmap.findings.security import detect_security_findings
from stackmap.nl_query import query_ir
from stackmap.parsers.base import ResourceCategory, StackMapIR, StackMapNode
from stackmap.parsers.terraform import TerraformParser
from stackmap.timeline import build_timeline_ir, write_snapshot
from stackmap.grouping.engine import build_group_aggregates
from stackmap.parsers.base import EdgeType, StackMapEdge, StackMapGroup


def _node(node_id: str, resource_type: str, props: dict | None = None) -> StackMapNode:
    return StackMapNode(
        id=node_id,
        name=node_id.split(".")[-1],
        resource_type=resource_type,
        provider="aws",
        category=ResourceCategory.SECURITY if "security" in resource_type or "iam" in resource_type else ResourceCategory.STORAGE,
        properties=props or {},
    )


def test_timeline_builder_records_snapshot_metadata(tmp_path: Path) -> None:
    before = StackMapIR(
        metadata={"scanned_at": "2026-04-15T10:00:00+00:00", "source_path": "before.json"},
        nodes=[_node("aws_s3_bucket.assets", "aws_s3_bucket")],
    )
    after = StackMapIR(
        metadata={"scanned_at": "2026-04-16T10:00:00+00:00", "source_path": "after.json"},
        nodes=[
            _node("aws_s3_bucket.assets", "aws_s3_bucket"),
            _node("aws_s3_bucket.logs", "aws_s3_bucket"),
        ],
    )
    write_snapshot(before, tmp_path)
    write_snapshot(after, tmp_path)

    timeline_ir = build_timeline_ir(tmp_path)

    assert timeline_ir.metadata["timeline_snapshot_count"] == 2
    assert timeline_ir.timeline is not None
    assert len(timeline_ir.timeline["snapshots"]) == 2
    assert timeline_ir.timeline["diffs"][0]["added"] == ["aws_s3_bucket.logs"]


def test_timeline_fixture_pair_has_diff_data(tmp_path: Path) -> None:
    before = StackMapIR.read_json("tests/fixtures/timeline-before.json")
    after = StackMapIR.read_json("tests/fixtures/timeline-after.json")
    before.metadata["scanned_at"] = "2026-04-15T10:00:00+00:00"
    after.metadata["scanned_at"] = "2026-04-16T10:00:00+00:00"
    write_snapshot(before, tmp_path)
    write_snapshot(after, tmp_path)

    timeline_ir = build_timeline_ir(tmp_path)

    assert timeline_ir.timeline is not None
    assert timeline_ir.timeline["diffs"][0]["summary"]["added"] >= 0
    assert "node_diffs" in timeline_ir.timeline["diffs"][0]


def test_security_findings_detect_wildcard_iam_and_open_sg() -> None:
    ir = StackMapIR(nodes=[
        _node("aws_iam_policy.admin", "aws_iam_policy", {
            "policy": {"Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]},
        }),
        _node("aws_security_group.ssh", "aws_security_group", {
            "ingress": [{"from_port": 22, "to_port": 22, "cidr_blocks": ["0.0.0.0/0"]}],
        }),
    ])

    pattern_ids = {finding.pattern_id for finding in detect_security_findings(ir)}

    assert "iam.wildcard_admin" in pattern_ids
    assert "sg.open_sensitive_port" in pattern_ids


def test_security_fixtures_detect_public_s3_and_open_sg() -> None:
    parser = TerraformParser()
    public_s3 = parser.parse("tests/fixtures/public-s3.tfstate")
    open_sg = parser.parse("tests/fixtures/open-sg.tfstate")

    s3_patterns = {finding.pattern_id for finding in detect_security_findings(public_s3)}
    sg_patterns = {finding.pattern_id for finding in detect_security_findings(open_sg)}

    assert "s3.public_bucket" in s3_patterns
    assert "sg.open_sensitive_port" in sg_patterns


def test_local_nl_query_matches_public_resources() -> None:
    ir = StackMapIR(nodes=[
        _node("aws_s3_bucket.public", "aws_s3_bucket", {"acl": "public-read"}),
        _node("aws_s3_bucket.private", "aws_s3_bucket", {"acl": "private"}),
    ])

    result = query_ir(ir, "show public resources")

    assert result["filter"]["nodeIds"] == ["aws_s3_bucket.public"]


def test_profile_discovery_reads_config_and_credentials(tmp_path: Path) -> None:
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[default]\nregion=us-east-1\n[profile prod]\nregion=us-east-1\n")
    (aws_dir / "credentials").write_text("[sandbox]\naws_access_key_id=x\naws_secret_access_key=y\n")

    assert discover_aws_profiles(tmp_path) == ["default", "prod", "sandbox"]


def test_group_aggregates_precompute_group_edges() -> None:
    ir = StackMapIR(
        nodes=[
            _node("a.1", "aws_lambda_function"),
            _node("b.1", "aws_dynamodb_table"),
        ],
        edges=[StackMapEdge(id="a-to-b", source="a.1", target="b.1", edge_type=EdgeType.READS_FROM)],
        groups=[
            StackMapGroup(id="group:a", name="A", group_type="smart_group", children=["a.1"]),
            StackMapGroup(id="group:b", name="B", group_type="smart_group", children=["b.1"]),
        ],
    )

    aggregates = build_group_aggregates(ir)

    assert len(aggregates["groups"]) == 2
    assert aggregates["edges_by_group"][0]["source"] == "group:a"
    assert aggregates["edges_by_group"][0]["target"] == "group:b"
