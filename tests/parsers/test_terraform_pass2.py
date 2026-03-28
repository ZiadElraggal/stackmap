"""Tests for Terraform parser Pass 2: Relationship inference."""

from pathlib import Path

from stackmap.parsers.base import EdgeType
from stackmap.parsers.terraform import TerraformParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _find_edge(
    edges: list, source_type: str, target_type: str, nodes: list, edge_type: EdgeType | None = None
) -> list:
    """Find edges between nodes of given resource types."""
    node_types = {n.id: n.resource_type for n in nodes}
    results = []
    for e in edges:
        src_type = node_types.get(e.source, "")
        tgt_type = node_types.get(e.target, "")
        if src_type == source_type and tgt_type == target_type:
            if edge_type is None or e.edge_type == edge_type:
                results.append(e)
    return results


def _find_edge_by_name(
    edges: list, source_name: str, target_name: str, nodes: list
) -> list:
    """Find edges between nodes with given names."""
    node_names = {n.id: n.name for n in nodes}
    results = []
    for e in edges:
        src_name = node_names.get(e.source, "")
        tgt_name = node_names.get(e.target, "")
        if src_name == source_name and tgt_name == target_name:
            results.append(e)
    return results


# --- Simple fixture tests ---


def test_simple_has_edges() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))
    assert len(ir.edges) > 0, "Parser should produce edges"


def test_simple_lambda_to_iam_role() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))
    edges = _find_edge(
        ir.edges, "aws_lambda_function", "aws_iam_role", ir.nodes, EdgeType.AUTHENTICATES
    )
    assert len(edges) == 2, f"Expected 2 Lambda→IAM Role edges, got {len(edges)}"


def test_simple_api_gateway_triggers_lambda() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))
    edges = _find_edge(
        ir.edges,
        "aws_api_gateway_rest_api",
        "aws_lambda_function",
        ir.nodes,
        EdgeType.TRIGGERS,
    )
    assert len(edges) >= 1, f"Expected API GW→Lambda trigger edges, got {len(edges)}"


def test_simple_lambda_to_log_group() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))
    edges = _find_edge(
        ir.edges, "aws_lambda_function", "aws_cloudwatch_log_group", ir.nodes, EdgeType.REFERENCES
    )
    assert len(edges) == 2, f"Expected 2 Lambda→LogGroup edges, got {len(edges)}"


def test_simple_no_duplicate_edges() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))
    edge_keys = [(e.source, e.target, e.edge_type) for e in ir.edges]
    assert len(edge_keys) == len(set(edge_keys)), "Duplicate edges found"


# --- Medium fixture tests ---


def test_medium_has_edges() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))
    assert len(ir.edges) > 0


def test_medium_sns_triggers_lambda() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))
    edges = _find_edge(
        ir.edges,
        "aws_sns_topic_subscription",
        "aws_lambda_function",
        ir.nodes,
        EdgeType.TRIGGERS,
    )
    assert len(edges) >= 1, f"Expected SNS→Lambda trigger edge, got {len(edges)}"


def test_medium_cloudfront_to_s3() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))
    edges = _find_edge(
        ir.edges,
        "aws_cloudfront_distribution",
        "aws_s3_bucket",
        ir.nodes,
        EdgeType.ROUTES_TO,
    )
    assert len(edges) >= 1, f"Expected CloudFront→S3 route edge, got {len(edges)}"


def test_medium_step_functions_to_iam() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))
    edges = _find_edge(
        ir.edges,
        "aws_sfn_state_machine",
        "aws_iam_role",
        ir.nodes,
        EdgeType.AUTHENTICATES,
    )
    assert len(edges) == 1, f"Expected 1 SFN→IAM Role edge, got {len(edges)}"


def test_medium_no_duplicate_edges() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))
    edge_keys = [(e.source, e.target, e.edge_type) for e in ir.edges]
    assert len(edge_keys) == len(set(edge_keys)), "Duplicate edges found"


# --- Complex fixture tests ---


def test_complex_has_edges() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    assert len(ir.edges) > 0


def test_complex_ecs_to_cluster() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    edges = _find_edge(
        ir.edges, "aws_ecs_service", "aws_ecs_cluster", ir.nodes, EdgeType.REFERENCES
    )
    assert len(edges) == 2, f"Expected 2 ECS Service→Cluster edges, got {len(edges)}"


def test_complex_subnet_to_vpc() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    edges = _find_edge(
        ir.edges, "aws_subnet", "aws_vpc", ir.nodes, EdgeType.CONTAINS
    )
    assert len(edges) >= 5, f"Expected ≥5 Subnet→VPC edges, got {len(edges)}"


def test_complex_no_duplicate_edges() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    edge_keys = [(e.source, e.target, e.edge_type) for e in ir.edges]
    assert len(edge_keys) == len(set(edge_keys)), "Duplicate edges found"


def test_complex_alb_edges() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    # ALB should have edges to subnets and security groups
    alb_edges = [e for e in ir.edges if any(
        n.resource_type == "aws_lb" and n.id == e.source for n in ir.nodes
    )]
    assert len(alb_edges) >= 1, f"Expected ALB edges, got {len(alb_edges)}"
