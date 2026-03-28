"""Tests for Terraform parser Pass 1: Node extraction."""

from pathlib import Path

from stackmap.parsers.base import ResourceCategory
from stackmap.parsers.terraform import TerraformParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_simple_fixture_node_count() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))
    assert len(ir.nodes) == 15


def test_simple_fixture_categories() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))

    # Find Lambda nodes
    lambda_nodes = [n for n in ir.nodes if n.resource_type == "aws_lambda_function"]
    assert len(lambda_nodes) == 2
    for n in lambda_nodes:
        assert n.category == ResourceCategory.COMPUTE

    # Find DynamoDB
    dynamo_nodes = [n for n in ir.nodes if n.resource_type == "aws_dynamodb_table"]
    assert len(dynamo_nodes) == 1
    assert dynamo_nodes[0].category == ResourceCategory.DATABASE

    # Find S3
    s3_nodes = [n for n in ir.nodes if n.resource_type == "aws_s3_bucket"]
    assert len(s3_nodes) == 1
    assert s3_nodes[0].category == ResourceCategory.STORAGE


def test_simple_fixture_names() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))

    names = {n.resource_type + ":" + n.name for n in ir.nodes}
    assert "aws_lambda_function:api-handler" in names
    assert "aws_lambda_function:data-processor" in names
    assert "aws_dynamodb_table:users-table" in names
    assert "aws_s3_bucket:stackmap-demo-assets" in names


def test_simple_fixture_metadata() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))

    assert ir.metadata["source_type"] == "terraform"
    assert ir.metadata["terraform_version"] == "1.7.2"
    assert ir.metadata["total_resources"] == 15


def test_medium_fixture_node_count() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))
    assert len(ir.nodes) == 28


def test_medium_fixture_step_functions() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))

    sfn_nodes = [n for n in ir.nodes if n.resource_type == "aws_sfn_state_machine"]
    assert len(sfn_nodes) == 1
    assert sfn_nodes[0].category == ResourceCategory.INTEGRATION


def test_complex_fixture_node_count() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    assert len(ir.nodes) == 59


def test_complex_fixture_vpc_nodes() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))

    vpc_nodes = [n for n in ir.nodes if n.resource_type == "aws_vpc"]
    assert len(vpc_nodes) == 2

    ecs_nodes = [n for n in ir.nodes if n.resource_type == "aws_ecs_service"]
    assert len(ecs_nodes) == 2


def test_position_hints() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))

    for node in ir.nodes:
        assert "tier" in node.position_hint
        assert "weight" in node.position_hint
        assert node.position_hint["tier"] in ["frontend", "api", "backend", "data"]
        assert isinstance(node.position_hint["weight"], int)
