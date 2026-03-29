"""Smoke tests for newly added tfstate fixtures."""

from pathlib import Path

from stackmap.parsers.terraform import TerraformParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_cdn_static_site_fixture_parses() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "cdn-static-site.tfstate"))
    assert len(ir.nodes) == 6
    assert len(ir.edges) >= 3
    assert any(n.resource_type == "aws_cloudfront_distribution" for n in ir.nodes)
    assert any(n.resource_type == "aws_s3_bucket" for n in ir.nodes)


def test_ecs_alb_service_fixture_parses() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "ecs-alb-service.tfstate"))
    assert len(ir.nodes) == 16
    assert len(ir.edges) >= 10
    assert any(n.resource_type == "aws_ecs_service" for n in ir.nodes)
    assert any(n.resource_type == "aws_lb" for n in ir.nodes)
    assert any(n.resource_type == "aws_db_instance" for n in ir.nodes)


def test_lambda_vpc_dataflow_fixture_parses() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "lambda-vpc-dataflow.tfstate"))
    assert len(ir.nodes) == 11
    assert len(ir.edges) >= 8
    assert any(n.resource_type == "aws_lambda_function" for n in ir.nodes)
    assert any(n.resource_type == "aws_dynamodb_table" for n in ir.nodes)
    assert any(n.resource_type == "aws_sqs_queue" for n in ir.nodes)
