"""Tests for dependency tracing / impact analysis."""

import pytest

from stackmap.graph.trace import TraceResult, find_node_by_name, trace_dependencies
from stackmap.parsers.base import (
    EdgeType,
    ResourceCategory,
    StackMapEdge,
    StackMapIR,
    StackMapNode,
)


def _make_node(id: str, name: str | None = None, rtype: str = "aws_lambda_function") -> StackMapNode:
    return StackMapNode(
        id=id,
        name=name or id,
        resource_type=rtype,
        provider="aws",
        category=ResourceCategory.SERVERLESS,
    )


def _make_edge(source: str, target: str, etype: EdgeType = EdgeType.TRIGGERS, label: str = "") -> StackMapEdge:
    return StackMapEdge(
        id=f"{source}->{target}",
        source=source,
        target=target,
        edge_type=etype,
        label=label,
    )


def _build_linear_chain_ir() -> StackMapIR:
    """API Gateway -> Lambda -> DynamoDB -> Kinesis Stream.

    A simple linear chain for basic tracing tests.
    """
    nodes = [
        _make_node("apigw", "api-gateway", "aws_api_gateway_rest_api"),
        _make_node("lambda", "process-payment", "aws_lambda_function"),
        _make_node("dynamo", "orders-table", "aws_dynamodb_table"),
        _make_node("kinesis", "analytics-stream", "aws_kinesis_stream"),
    ]
    edges = [
        _make_edge("apigw", "lambda", EdgeType.TRIGGERS, "invokes"),
        _make_edge("lambda", "dynamo", EdgeType.WRITES_TO, "writes orders"),
        _make_edge("dynamo", "kinesis", EdgeType.TRIGGERS, "streams changes"),
    ]
    return StackMapIR(nodes=nodes, edges=edges)


def _build_fan_out_ir() -> StackMapIR:
    """Lambda that fans out to multiple downstream services.

    Lambda -> DynamoDB, S3, SNS -> SQS
    """
    nodes = [
        _make_node("apigw", "api-gateway", "aws_api_gateway_rest_api"),
        _make_node("lambda", "handler", "aws_lambda_function"),
        _make_node("dynamo", "table", "aws_dynamodb_table"),
        _make_node("s3", "bucket", "aws_s3_bucket"),
        _make_node("sns", "topic", "aws_sns_topic"),
        _make_node("sqs", "queue", "aws_sqs_queue"),
        _make_node("role", "lambda-role", "aws_iam_role"),
    ]
    edges = [
        _make_edge("apigw", "lambda", EdgeType.TRIGGERS),
        _make_edge("lambda", "dynamo", EdgeType.WRITES_TO),
        _make_edge("lambda", "s3", EdgeType.WRITES_TO),
        _make_edge("lambda", "sns", EdgeType.WRITES_TO),
        _make_edge("sns", "sqs", EdgeType.TRIGGERS),
        _make_edge("lambda", "role", EdgeType.AUTHENTICATES),
    ]
    return StackMapIR(nodes=nodes, edges=edges)


def _build_ir_with_contains() -> StackMapIR:
    """IR with CONTAINS edges that should be excluded from tracing."""
    nodes = [
        _make_node("vpc", "main-vpc", "aws_vpc"),
        _make_node("subnet", "private-subnet", "aws_subnet"),
        _make_node("lambda", "fn", "aws_lambda_function"),
        _make_node("dynamo", "table", "aws_dynamodb_table"),
    ]
    edges = [
        _make_edge("vpc", "subnet", EdgeType.CONTAINS),
        _make_edge("subnet", "lambda", EdgeType.CONTAINS),
        _make_edge("lambda", "dynamo", EdgeType.WRITES_TO),
    ]
    return StackMapIR(nodes=nodes, edges=edges)


class TestTraceBasic:
    def test_trace_linear_downstream(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "lambda", direction="downstream")

        assert result.origin_id == "lambda"
        downstream_ids = {h.node_id for h in result.downstream}
        assert "dynamo" in downstream_ids
        assert "kinesis" in downstream_ids
        assert "apigw" not in downstream_ids
        assert result.blast_radius == 2

    def test_trace_linear_upstream(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "lambda", direction="upstream")

        upstream_ids = {h.node_id for h in result.upstream}
        assert "apigw" in upstream_ids
        assert "dynamo" not in upstream_ids

    def test_trace_both_directions(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "lambda", direction="both")

        upstream_ids = {h.node_id for h in result.upstream}
        downstream_ids = {h.node_id for h in result.downstream}
        assert "apigw" in upstream_ids
        assert "dynamo" in downstream_ids
        assert "kinesis" in downstream_ids

    def test_trace_from_leaf_no_downstream(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "kinesis", direction="downstream")

        assert result.downstream == []
        assert result.blast_radius == 0

    def test_trace_from_root_no_upstream(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "apigw", direction="upstream")

        assert result.upstream == []

    def test_trace_invalid_origin_raises(self) -> None:
        ir = _build_linear_chain_ir()
        with pytest.raises(ValueError, match="Origin node not found"):
            trace_dependencies(ir, "nonexistent")


class TestTraceFanOut:
    def test_blast_radius_fan_out(self) -> None:
        ir = _build_fan_out_ir()
        result = trace_dependencies(ir, "lambda", direction="downstream")

        downstream_ids = {h.node_id for h in result.downstream}
        assert "dynamo" in downstream_ids
        assert "s3" in downstream_ids
        assert "sns" in downstream_ids
        assert "sqs" in downstream_ids
        # role is also downstream (lambda -> role via AUTHENTICATES edge)
        assert "role" in downstream_ids
        assert result.blast_radius == 5

    def test_upstream_of_lambda(self) -> None:
        ir = _build_fan_out_ir()
        result = trace_dependencies(ir, "lambda", direction="upstream")

        upstream_ids = {h.node_id for h in result.upstream}
        assert "apigw" in upstream_ids
        # role is downstream (lambda -> role), not upstream
        assert "role" not in upstream_ids


class TestTraceDepth:
    def test_max_depth_limits_traversal(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "apigw", max_depth=1, direction="downstream")

        downstream_ids = {h.node_id for h in result.downstream}
        assert "lambda" in downstream_ids
        assert "dynamo" not in downstream_ids  # depth 2, filtered out

    def test_max_depth_zero_returns_empty(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "lambda", max_depth=0)

        assert result.upstream == []
        assert result.downstream == []


class TestContainsExclusion:
    def test_contains_edges_excluded(self) -> None:
        ir = _build_ir_with_contains()
        result = trace_dependencies(ir, "lambda", direction="both")

        all_ids = {h.node_id for h in result.upstream + result.downstream}
        # CONTAINS edges should not be followed
        assert "vpc" not in all_ids
        assert "subnet" not in all_ids
        # Real functional edge should be followed
        assert "dynamo" in {h.node_id for h in result.downstream}


class TestCriticalPath:
    def test_critical_path_linear(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "apigw", direction="downstream")

        assert result.critical_path[0] == "apigw"
        assert len(result.critical_path) == 4  # full chain
        assert result.critical_path_length == 3

    def test_critical_path_single_node(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "kinesis", direction="downstream")

        assert result.critical_path == ["kinesis"]
        assert result.critical_path_length == 0


class TestEdgeTypeFilter:
    def test_include_only_triggers(self) -> None:
        ir = _build_fan_out_ir()
        result = trace_dependencies(
            ir, "lambda", direction="downstream",
            include_edge_types={EdgeType.TRIGGERS},
        )

        downstream_ids = {h.node_id for h in result.downstream}
        # Lambda doesn't TRIGGER anything directly — apigw triggers lambda
        # But SNS triggers SQS — however lambda->sns is WRITES_TO, so sns not reachable
        assert "dynamo" not in downstream_ids
        assert "s3" not in downstream_ids


class TestFindNode:
    def test_find_by_exact_id(self) -> None:
        ir = _build_linear_chain_ir()
        node = find_node_by_name(ir, "lambda")
        assert node is not None
        assert node.id == "lambda"

    def test_find_by_exact_name(self) -> None:
        ir = _build_linear_chain_ir()
        node = find_node_by_name(ir, "process-payment")
        assert node is not None
        assert node.id == "lambda"

    def test_find_by_partial_name(self) -> None:
        ir = _build_linear_chain_ir()
        node = find_node_by_name(ir, "payment")
        assert node is not None
        assert node.id == "lambda"

    def test_find_not_found(self) -> None:
        ir = _build_linear_chain_ir()
        assert find_node_by_name(ir, "nonexistent") is None


class TestTraceToDict:
    def test_serialization(self) -> None:
        ir = _build_linear_chain_ir()
        result = trace_dependencies(ir, "lambda")
        d = result.to_dict()

        assert d["origin_id"] == "lambda"
        assert isinstance(d["upstream"], list)
        assert isinstance(d["downstream"], list)
        assert isinstance(d["blast_radius"], int)
        assert isinstance(d["critical_path"], list)


class TestTraceWithFixture:
    """Test tracing using a real parsed fixture if available."""

    def test_trace_simple_lambda_api(self) -> None:
        """Trace from a real Terraform state file."""
        from pathlib import Path

        fixture = Path(__file__).parent.parent / "fixtures" / "simple-lambda-api.tfstate"
        if not fixture.exists():
            pytest.skip("Fixture not available")

        from stackmap.parsers.registry import parse_source

        _, ir = parse_source(str(fixture))
        assert len(ir.nodes) > 0

        # Find a lambda function to trace from
        lambda_nodes = [n for n in ir.nodes if "lambda" in n.resource_type]
        if not lambda_nodes:
            pytest.skip("No lambda nodes in fixture")

        result = trace_dependencies(ir, lambda_nodes[0].id)
        # Just verify it runs without error and produces valid output
        assert result.origin_id == lambda_nodes[0].id
        assert isinstance(result.blast_radius, int)
        assert len(result.critical_path) >= 1
