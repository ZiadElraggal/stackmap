"""Demo-readiness tests for customer-facing architecture clarity."""

from pathlib import Path

from stackmap.parsers.base import EdgeType
from stackmap.parsers.terraform import TerraformParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_medium_fixture_has_expected_customer_story_edges() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "medium-step-functions.tfstate"))
    node_types = {n.id: n.resource_type for n in ir.nodes}

    flow_edges = [
        e
        for e in ir.edges
        if e.edge_type in {
            EdgeType.TRIGGERS,
            EdgeType.WRITES_TO,
            EdgeType.READS_FROM,
            EdgeType.ROUTES_TO,
        }
    ]
    assert len(flow_edges) >= 12

    assert any(
        node_types.get(e.source) == "aws_route53_record"
        and node_types.get(e.target) == "aws_cloudfront_distribution"
        and e.edge_type == EdgeType.ROUTES_TO
        for e in ir.edges
    )
    assert any(
        node_types.get(e.source) == "aws_sfn_state_machine"
        and node_types.get(e.target) == "aws_lambda_function"
        and e.edge_type == EdgeType.TRIGGERS
        for e in ir.edges
    )
    assert any(
        node_types.get(e.source) == "aws_lambda_function"
        and node_types.get(e.target) == "aws_dynamodb_table"
        and e.edge_type in {EdgeType.WRITES_TO, EdgeType.READS_FROM}
        for e in ir.edges
    )


def test_simple_fixture_keeps_core_resources_for_architecture_view() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "simple-lambda-api.tfstate"))
    types = {n.resource_type for n in ir.nodes}
    assert "aws_api_gateway_rest_api" in types
    assert "aws_lambda_function" in types
    assert "aws_dynamodb_table" in types
    assert "aws_s3_bucket" in types


def test_no_duplicate_edges_in_customer_fixtures() -> None:
    parser = TerraformParser()
    for fixture in ("simple-lambda-api.tfstate", "medium-step-functions.tfstate"):
        ir = parser.parse(str(FIXTURES / fixture))
        edge_keys = [(e.source, e.target, e.edge_type.value) for e in ir.edges]
        assert len(edge_keys) == len(set(edge_keys)), f"Duplicate edges found in {fixture}"
