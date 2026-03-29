"""Phase 2 quality gate: expanded Terraform relationship extraction."""

from pathlib import Path

from stackmap.parsers.base import EdgeType
from stackmap.parsers.terraform import TerraformParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _count_edges(
    ir,
    source_type: str,
    target_type: str,
    edge_type: EdgeType,
) -> int:
    node_types = {n.id: n.resource_type for n in ir.nodes}
    return sum(
        1
        for e in ir.edges
        if e.edge_type == edge_type
        and node_types.get(e.source) == source_type
        and node_types.get(e.target) == target_type
    )


def test_phase2_complex_fixture_extracts_lb_target_group_flow() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    assert _count_edges(ir, "aws_lb_listener", "aws_lb_target_group", EdgeType.ROUTES_TO) >= 1
    assert _count_edges(ir, "aws_lb_listener_rule", "aws_lb_target_group", EdgeType.ROUTES_TO) >= 1
    assert _count_edges(ir, "aws_ecs_service", "aws_lb_target_group", EdgeType.ROUTES_TO) >= 2


def test_phase2_complex_fixture_extracts_network_join_edges() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    assert _count_edges(ir, "aws_route_table_association", "aws_route_table", EdgeType.REFERENCES) >= 4
    assert _count_edges(ir, "aws_route_table_association", "aws_subnet", EdgeType.REFERENCES) >= 4
    assert _count_edges(ir, "aws_nat_gateway", "aws_eip", EdgeType.REFERENCES) >= 1


def test_phase2_extracts_route53_zone_reference_when_zone_exists() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    assert _count_edges(ir, "aws_route53_record", "aws_route53_zone", EdgeType.REFERENCES) >= 1


def test_phase2_extracts_api_stage_to_deployment_reference() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "simple-lambda-api.tfstate"))
    assert _count_edges(ir, "aws_api_gateway_stage", "aws_api_gateway_deployment", EdgeType.REFERENCES) >= 1
