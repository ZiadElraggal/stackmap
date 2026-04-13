"""Tests for drift normalizer."""

from stackmap.drift.normalizer import (
    match_resources,
    normalize_ir,
)
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
        category=ResourceCategory.SERVERLESS,
        properties=props or {},
        metadata=meta or {},
    )


class TestNormalizeIR:
    def test_basic_normalization(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "my-lambda", "aws_lambda_function", {"runtime": "python3.12"}),
        ])
        resources = normalize_ir(ir)
        assert len(resources) == 1
        res = list(resources.values())[0]
        assert res.resource_type == "aws_lambda_function"
        assert res.name == "my-lambda"
        assert res.original_id == "fn1"

    def test_arn_based_canonical_id(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "my-lambda", "aws_lambda_function", {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:my-lambda",
            }),
        ])
        resources = normalize_ir(ir)
        res = list(resources.values())[0]
        assert res.canonical_id == "arn:aws:lambda:us-east-1:123456789012:function:my-lambda"

    def test_cfn_property_normalization(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "my-lambda", "aws_lambda_function", {
                "MemorySize": 512,
                "Timeout": 30,
            }),
        ])
        resources = normalize_ir(ir)
        res = list(resources.values())[0]
        assert "memory_size" in res.properties
        assert res.properties["memory_size"] == 512

    def test_relationships_normalized(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("fn1", "handler", "aws_lambda_function"),
                _node("db1", "table", "aws_dynamodb_table"),
            ],
            edges=[
                StackMapEdge(id="e1", source="fn1", target="db1", edge_type=EdgeType.WRITES_TO),
            ],
        )
        resources = normalize_ir(ir)
        fn_res = [r for r in resources.values() if r.original_id == "fn1"][0]
        assert len(fn_res.relationships) > 0


class TestMatchResources:
    def test_exact_canonical_match(self) -> None:
        iac_ir = StackMapIR(nodes=[
            _node("fn1", "my-lambda", "aws_lambda_function", {
                "arn": "arn:aws:lambda:us-east-1:123:function:my-lambda",
            }),
        ])
        live_ir = StackMapIR(nodes=[
            _node("live-fn1", "my-lambda", "aws_lambda_function", {
                "arn": "arn:aws:lambda:us-east-1:123:function:my-lambda",
            }),
        ])

        iac_resources = normalize_ir(iac_ir, "iac")
        live_resources = normalize_ir(live_ir, "live")
        matched, iac_only, live_only = match_resources(iac_resources, live_resources)

        assert len(matched) == 1
        assert len(iac_only) == 0
        assert len(live_only) == 0

    def test_type_name_fallback_match(self) -> None:
        iac_ir = StackMapIR(nodes=[
            _node("fn1", "my-lambda", "aws_lambda_function"),
        ])
        live_ir = StackMapIR(nodes=[
            _node("live-fn1", "my-lambda", "aws_lambda_function"),
        ])

        iac_resources = normalize_ir(iac_ir, "iac")
        live_resources = normalize_ir(live_ir, "live")
        matched, iac_only, live_only = match_resources(iac_resources, live_resources)

        assert len(matched) == 1

    def test_unmatched_resources(self) -> None:
        iac_ir = StackMapIR(nodes=[
            _node("fn1", "lambda-a", "aws_lambda_function"),
            _node("fn2", "lambda-b", "aws_lambda_function"),
        ])
        live_ir = StackMapIR(nodes=[
            _node("fn1", "lambda-a", "aws_lambda_function"),
            _node("fn3", "lambda-c", "aws_lambda_function"),
        ])

        iac_resources = normalize_ir(iac_ir, "iac")
        live_resources = normalize_ir(live_ir, "live")
        matched, iac_only, live_only = match_resources(iac_resources, live_resources)

        assert len(matched) == 1
        assert len(iac_only) == 1
        assert len(live_only) == 1
        assert iac_only[0].name == "lambda-b"
        assert live_only[0].name == "lambda-c"
