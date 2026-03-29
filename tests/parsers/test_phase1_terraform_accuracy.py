"""Phase 1 quality gate: Terraform parsing accuracy and relationship integrity."""

from pathlib import Path

import pytest

from stackmap.parsers.base import EdgeType
from stackmap.parsers.terraform import TerraformParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def parser() -> TerraformParser:
    return TerraformParser()


def _edge_count(ir, source_type: str, target_type: str, edge_type: EdgeType) -> int:
    node_types = {n.id: n.resource_type for n in ir.nodes}
    return sum(
        1
        for e in ir.edges
        if e.edge_type == edge_type
        and node_types.get(e.source) == source_type
        and node_types.get(e.target) == target_type
    )


@pytest.mark.parametrize(
    ("fixture", "min_nodes", "min_edges"),
    [
        ("simple-lambda-api.tfstate", 12, 8),
        ("medium-step-functions.tfstate", 24, 24),
        ("complex-multi-vpc.tfstate", 50, 45),
        ("cdn-static-site.tfstate", 5, 3),
        ("ecs-alb-service.tfstate", 14, 12),
        ("lambda-vpc-dataflow.tfstate", 10, 10),
    ],
)
def test_phase1_fixtures_parse_with_expected_scale(
    parser: TerraformParser, fixture: str, min_nodes: int, min_edges: int
) -> None:
    ir = parser.parse(str(FIXTURES / fixture))
    assert len(ir.nodes) >= min_nodes
    assert len(ir.edges) >= min_edges


@pytest.mark.parametrize(
    ("fixture", "required_checks"),
    [
        (
            "simple-lambda-api.tfstate",
            [
                ("aws_api_gateway_rest_api", "aws_lambda_function", EdgeType.TRIGGERS, 2),
                ("aws_lambda_function", "aws_iam_role", EdgeType.AUTHENTICATES, 2),
            ],
        ),
        (
            "medium-step-functions.tfstate",
            [
                ("aws_route53_record", "aws_cloudfront_distribution", EdgeType.ROUTES_TO, 1),
                ("aws_sfn_state_machine", "aws_lambda_function", EdgeType.TRIGGERS, 3),
                ("aws_lambda_function", "aws_dynamodb_table", EdgeType.WRITES_TO, 2),
                ("aws_lambda_function", "aws_s3_bucket", EdgeType.WRITES_TO, 2),
            ],
        ),
        (
            "cdn-static-site.tfstate",
            [
                ("aws_route53_record", "aws_cloudfront_distribution", EdgeType.ROUTES_TO, 1),
            ],
        ),
        (
            "ecs-alb-service.tfstate",
            [
                ("aws_route53_record", "aws_lb", EdgeType.ROUTES_TO, 1),
                ("aws_ecs_service", "aws_ecs_cluster", EdgeType.REFERENCES, 1),
                ("aws_ecs_service", "aws_ecs_task_definition", EdgeType.REFERENCES, 1),
            ],
        ),
        (
            "lambda-vpc-dataflow.tfstate",
            [
                ("aws_subnet", "aws_vpc", EdgeType.CONTAINS, 2),
                ("aws_lambda_function", "aws_subnet", EdgeType.REFERENCES, 2),
                ("aws_lambda_function", "aws_dynamodb_table", EdgeType.WRITES_TO, 1),
            ],
        ),
        (
            "complex-multi-vpc.tfstate",
            [
                ("aws_subnet", "aws_vpc", EdgeType.CONTAINS, 4),
                ("aws_ecs_service", "aws_ecs_cluster", EdgeType.REFERENCES, 2),
                ("aws_lambda_function", "aws_subnet", EdgeType.REFERENCES, 4),
            ],
        ),
    ],
)
def test_phase1_core_relationships_are_detected(
    parser: TerraformParser,
    fixture: str,
    required_checks: list[tuple[str, str, EdgeType, int]],
) -> None:
    ir = parser.parse(str(FIXTURES / fixture))
    for source_type, target_type, edge_type, minimum in required_checks:
        count = _edge_count(ir, source_type, target_type, edge_type)
        assert (
            count >= minimum
        ), f"{fixture}: expected >= {minimum} {source_type}->{target_type} [{edge_type.value}], found {count}"


def test_phase1_no_dangling_edges_across_core_fixtures(parser: TerraformParser) -> None:
    fixtures = (
        "simple-lambda-api.tfstate",
        "medium-step-functions.tfstate",
        "complex-multi-vpc.tfstate",
        "cdn-static-site.tfstate",
        "ecs-alb-service.tfstate",
        "lambda-vpc-dataflow.tfstate",
    )
    for fixture in fixtures:
        ir = parser.parse(str(FIXTURES / fixture))
        node_ids = {n.id for n in ir.nodes}
        dangling = [
            (e.source, e.target, e.edge_type.value)
            for e in ir.edges
            if e.source not in node_ids or e.target not in node_ids
        ]
        assert not dangling, f"{fixture}: found dangling edges {dangling}"
