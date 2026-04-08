"""Tests for suspicious pattern detection."""

from stackmap.analysis.patterns import Severity, analyze_patterns
from stackmap.parsers.base import (
    EdgeType,
    ResourceCategory,
    StackMapEdge,
    StackMapIR,
    StackMapNode,
)


def _node(id: str, name: str, rtype: str, props: dict | None = None, meta: dict | None = None) -> StackMapNode:
    return StackMapNode(
        id=id,
        name=name,
        resource_type=rtype,
        provider="aws",
        category=ResourceCategory.OTHER,
        properties=props or {},
        metadata=meta or {},
    )


def _edge(src: str, tgt: str, etype: EdgeType = EdgeType.TRIGGERS) -> StackMapEdge:
    return StackMapEdge(id=f"{src}->{tgt}", source=src, target=tgt, edge_type=etype)


class TestOrphanedResources:
    def test_detects_orphan(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("fn1", "handler", "aws_lambda_function"),
                _node("s3", "orphan-bucket", "aws_s3_bucket"),
            ],
            edges=[_edge("fn1", "fn1")],  # self-edge only connects fn1
        )
        findings = analyze_patterns(ir)
        orphans = [f for f in findings if f.pattern_id == "orphaned-resource"]
        assert len(orphans) >= 1
        assert any("orphan-bucket" in f.description for f in orphans)

    def test_expected_leaf_not_orphan(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("policy", "my-policy", "aws_iam_policy"),
                _node("log", "my-log", "aws_cloudwatch_log_group"),
            ],
            edges=[],
        )
        findings = analyze_patterns(ir)
        orphans = [f for f in findings if f.pattern_id == "orphaned-resource"]
        assert len(orphans) == 0

    def test_connected_not_orphan(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("fn1", "handler", "aws_lambda_function"),
                _node("db1", "table", "aws_dynamodb_table"),
            ],
            edges=[_edge("fn1", "db1", EdgeType.WRITES_TO)],
        )
        findings = analyze_patterns(ir)
        orphans = [f for f in findings if f.pattern_id == "orphaned-resource"]
        assert len(orphans) == 0


class TestUnusedLoadBalancers:
    def test_lb_with_no_targets(self) -> None:
        ir = StackMapIR(
            nodes=[_node("lb1", "old-alb", "aws_lb")],
            edges=[],
        )
        findings = analyze_patterns(ir)
        unused = [f for f in findings if f.pattern_id == "unused-lb"]
        assert len(unused) == 1

    def test_lb_with_targets_ok(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("lb1", "active-alb", "aws_lb"),
                _node("ecs1", "service", "aws_ecs_service"),
            ],
            edges=[_edge("lb1", "ecs1", EdgeType.ROUTES_TO)],
        )
        findings = analyze_patterns(ir)
        unused = [f for f in findings if f.pattern_id == "unused-lb"]
        assert len(unused) == 0


class TestCrossRegion:
    def test_unexpected_cross_region(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("fn1", "handler", "aws_lambda_function", meta={"region": "us-east-1"}),
                _node("db1", "table", "aws_dynamodb_table", meta={"region": "eu-west-1"}),
            ],
            edges=[_edge("fn1", "db1", EdgeType.WRITES_TO)],
        )
        findings = analyze_patterns(ir)
        cross = [f for f in findings if f.pattern_id == "cross-region"]
        assert len(cross) == 1

    def test_global_service_not_flagged(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("cf1", "cdn", "aws_cloudfront_distribution", meta={"region": "us-east-1"}),
                _node("s3", "bucket", "aws_s3_bucket", meta={"region": "eu-west-1"}),
            ],
            edges=[_edge("cf1", "s3", EdgeType.ROUTES_TO)],
        )
        findings = analyze_patterns(ir)
        cross = [f for f in findings if f.pattern_id == "cross-region"]
        assert len(cross) == 0

    def test_same_region_not_flagged(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("fn1", "handler", "aws_lambda_function", meta={"region": "us-east-1"}),
                _node("db1", "table", "aws_dynamodb_table", meta={"region": "us-east-1"}),
            ],
            edges=[_edge("fn1", "db1", EdgeType.WRITES_TO)],
        )
        findings = analyze_patterns(ir)
        cross = [f for f in findings if f.pattern_id == "cross-region"]
        assert len(cross) == 0


class TestPublicExposure:
    def test_public_s3_bucket(self) -> None:
        ir = StackMapIR(nodes=[
            _node("s3", "public-bucket", "aws_s3_bucket", {"acl": "public-read"}),
        ])
        findings = analyze_patterns(ir)
        exposure = [f for f in findings if f.pattern_id == "public-exposure"]
        assert len(exposure) >= 1
        assert exposure[0].severity == Severity.CRITICAL

    def test_open_security_group(self) -> None:
        ir = StackMapIR(nodes=[
            _node("sg1", "web-sg", "aws_security_group", {
                "ingress": [{"from_port": 22, "to_port": 22, "cidr_blocks": ["0.0.0.0/0"]}],
            }),
        ])
        findings = analyze_patterns(ir)
        exposure = [f for f in findings if f.pattern_id == "public-exposure"]
        assert len(exposure) >= 1
        assert exposure[0].severity == Severity.CRITICAL

    def test_web_ports_not_flagged(self) -> None:
        ir = StackMapIR(nodes=[
            _node("sg1", "web-sg", "aws_security_group", {
                "ingress": [{"from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"]}],
            }),
        ])
        findings = analyze_patterns(ir)
        exposure = [f for f in findings if f.pattern_id == "public-exposure"]
        assert len(exposure) == 0

    def test_public_rds(self) -> None:
        ir = StackMapIR(nodes=[
            _node("db1", "prod-db", "aws_db_instance", {"publicly_accessible": True}),
        ])
        findings = analyze_patterns(ir)
        exposure = [f for f in findings if f.pattern_id == "public-exposure"]
        assert len(exposure) >= 1


class TestUnencryptedStorage:
    def test_s3_no_encryption(self) -> None:
        ir = StackMapIR(nodes=[
            _node("s3", "bucket", "aws_s3_bucket", {}),
        ])
        findings = analyze_patterns(ir)
        unenc = [f for f in findings if f.pattern_id == "unencrypted-storage"]
        assert len(unenc) >= 1

    def test_s3_with_encryption_ok(self) -> None:
        ir = StackMapIR(nodes=[
            _node("s3", "bucket", "aws_s3_bucket", {
                "server_side_encryption_configuration": {"rule": {}},
            }),
        ])
        findings = analyze_patterns(ir)
        unenc = [f for f in findings if f.pattern_id == "unencrypted-storage" and "s3" in str(f.node_ids)]
        assert len(unenc) == 0

    def test_rds_no_encryption(self) -> None:
        ir = StackMapIR(nodes=[
            _node("db1", "my-db", "aws_db_instance", {"storage_encrypted": False}),
        ])
        findings = analyze_patterns(ir)
        unenc = [f for f in findings if f.pattern_id == "unencrypted-storage" and "db1" in f.node_ids]
        assert len(unenc) >= 1


class TestOversizedResources:
    def test_oversized_lambda(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "big-fn", "aws_lambda_function", {"memory_size": 4096, "timeout": 5}),
        ])
        findings = analyze_patterns(ir)
        oversized = [f for f in findings if f.pattern_id == "oversized-resource"]
        assert len(oversized) == 1

    def test_normal_lambda_ok(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "fn", "aws_lambda_function", {"memory_size": 256, "timeout": 30}),
        ])
        findings = analyze_patterns(ir)
        oversized = [f for f in findings if f.pattern_id == "oversized-resource"]
        assert len(oversized) == 0


class TestFindingSerialization:
    def test_to_dict(self) -> None:
        ir = StackMapIR(nodes=[
            _node("s3", "bucket", "aws_s3_bucket", {"acl": "public-read"}),
        ])
        findings = analyze_patterns(ir)
        for f in findings:
            d = f.to_dict()
            assert "id" in d
            assert "pattern_id" in d
            assert "severity" in d
            assert "node_ids" in d


class TestEmptyIR:
    def test_no_findings_on_empty(self) -> None:
        ir = StackMapIR()
        findings = analyze_patterns(ir)
        assert findings == []
