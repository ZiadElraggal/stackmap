"""Phase 5 quality gate: SAM template support."""

from pathlib import Path

from stackmap.parsers.base import EdgeType, ResourceCategory
from stackmap.parsers.sam import SamParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_sam_simple_fixture_parses() -> None:
    ir = SamParser().parse(str(FIXTURES / "sam-simple.json"))
    assert ir.metadata["source_type"] == "sam"
    assert len(ir.nodes) >= 4
    assert len(ir.edges) >= 3


def test_sam_categories_are_mapped() -> None:
    ir = SamParser().parse(str(FIXTURES / "sam-simple.json"))
    categories = {n.resource_type: n.category for n in ir.nodes}
    assert categories["AWS::Serverless::Function"] == ResourceCategory.COMPUTE
    assert categories["AWS::Serverless::Api"] == ResourceCategory.INTEGRATION
    assert categories["AWS::Serverless::StateMachine"] == ResourceCategory.INTEGRATION


def test_sam_event_and_role_edges() -> None:
    ir = SamParser().parse(str(FIXTURES / "sam-simple.json"))
    by_type = {n.resource_type: n.id for n in ir.nodes}
    api_id = by_type["AWS::Serverless::Api"]
    fn_id = by_type["AWS::Serverless::Function"]
    role_id = by_type["AWS::IAM::Role"]

    edge_keys = {(e.source, e.target, e.edge_type) for e in ir.edges}
    assert (api_id, fn_id, EdgeType.TRIGGERS) in edge_keys
    assert (fn_id, role_id, EdgeType.AUTHENTICATES) in edge_keys


def test_sam_standard_serverless_fixture_parses() -> None:
    ir = SamParser().parse(str(FIXTURES / "sam-standard-serverless.json"))
    assert ir.metadata["source_type"] == "sam"

    by_type = {n.resource_type: n.id for n in ir.nodes}
    api_id = by_type["AWS::Serverless::HttpApi"]
    fn_id = by_type["AWS::Serverless::Function"]
    role_id = by_type["AWS::IAM::Role"]
    table_id = by_type["AWS::DynamoDB::Table"]
    queue_id = by_type["AWS::SQS::Queue"]

    edge_keys = {(e.source, e.target, e.edge_type) for e in ir.edges}
    assert (api_id, fn_id, EdgeType.TRIGGERS) in edge_keys
    assert (fn_id, role_id, EdgeType.AUTHENTICATES) in edge_keys
    assert (fn_id, table_id, EdgeType.REFERENCES) in edge_keys
    assert (fn_id, queue_id, EdgeType.REFERENCES) in edge_keys


def test_sam_complex_fixture_supports_architecture_mode_signals() -> None:
    ir = SamParser().parse(str(FIXTURES / "sam-complex-serverless.json"))
    assert ir.metadata["source_type"] == "sam"
    assert len(ir.nodes) >= 10
    assert len(ir.edges) >= 10

    helper_nodes = [n for n in ir.nodes if n.position_hint.get("is_helper")]
    assert len(helper_nodes) >= 4
    assert any(n.position_hint.get("logical_parent") for n in helper_nodes)

    by_type = {n.resource_type: n.id for n in ir.nodes}
    http_api_id = by_type["AWS::Serverless::HttpApi"]
    orders_fn_id = next(
        n.id for n in ir.nodes if n.resource_type == "AWS::Serverless::Function" and n.name == "stackmap-orders-api"
    )

    edge_keys = {(e.source, e.target, e.edge_type) for e in ir.edges}
    assert (http_api_id, orders_fn_id, EdgeType.TRIGGERS) in edge_keys
