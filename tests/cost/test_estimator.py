"""Tests for cost estimation engine."""

import json
from pathlib import Path

from stackmap.cost.estimator import CostReport, annotate_ir_with_costs, estimate_costs
from stackmap.parsers.base import (
    EdgeType,
    ResourceCategory,
    StackMapEdge,
    StackMapIR,
    StackMapNode,
)


def _node(id: str, name: str, rtype: str, props: dict | None = None,
          category: ResourceCategory = ResourceCategory.SERVERLESS) -> StackMapNode:
    return StackMapNode(
        id=id,
        name=name,
        resource_type=rtype,
        provider="aws",
        category=category,
        properties=props or {},
    )


def _edge(src: str, tgt: str, etype: EdgeType = EdgeType.TRIGGERS) -> StackMapEdge:
    return StackMapEdge(id=f"{src}->{tgt}", source=src, target=tgt, edge_type=etype)


class TestPricingDB:
    def test_pricing_db_loads(self) -> None:
        db_path = Path(__file__).parent.parent.parent / "stackmap" / "cost" / "pricing_db.json"
        assert db_path.exists()
        with open(db_path) as f:
            data = json.load(f)
        assert "version" in data
        assert "services" in data
        assert len(data["services"]) > 10

    def test_all_services_have_required_fields(self) -> None:
        db_path = Path(__file__).parent.parent.parent / "stackmap" / "cost" / "pricing_db.json"
        with open(db_path) as f:
            data = json.load(f)
        for service_type, config in data["services"].items():
            assert "pricing_model" in config, f"{service_type} missing pricing_model"


class TestLambdaEstimate:
    def test_lambda_with_memory(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "handler", "aws_lambda_function", {"memory_size": 256}),
        ])
        report = estimate_costs(ir)
        est = report.by_node["fn1"]
        assert est.monthly_estimate > 0
        assert est.confidence in ("medium", "high")
        assert est.pricing_model == "invocation"

    def test_lambda_default_memory(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "handler", "aws_lambda_function"),
        ])
        report = estimate_costs(ir)
        est = report.by_node["fn1"]
        assert est.monthly_estimate > 0

    def test_lambda_high_memory(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "big", "aws_lambda_function", {"memory_size": 10240}),
        ])
        report = estimate_costs(ir)
        est = report.by_node["fn1"]
        assert est.monthly_estimate >= 60  # Should be expensive


class TestRDSEstimate:
    def test_rds_known_instance_type(self) -> None:
        ir = StackMapIR(nodes=[
            _node("db1", "prod-db", "aws_db_instance", {"instance_class": "db.r6g.xlarge"},
                  category=ResourceCategory.DATABASE),
        ])
        report = estimate_costs(ir)
        est = report.by_node["db1"]
        assert est.monthly_estimate > 200
        assert est.confidence == "high"

    def test_rds_multi_az(self) -> None:
        ir = StackMapIR(nodes=[
            _node("db1", "prod-db", "aws_db_instance",
                  {"instance_class": "db.t3.medium", "multi_az": True},
                  category=ResourceCategory.DATABASE),
        ])
        report = estimate_costs(ir)
        est = report.by_node["db1"]
        # Multi-AZ should roughly double the cost
        assert est.monthly_estimate > 90

    def test_rds_unknown_instance_type(self) -> None:
        ir = StackMapIR(nodes=[
            _node("db1", "db", "aws_db_instance", {"instance_class": "db.z99.mega"},
                  category=ResourceCategory.DATABASE),
        ])
        report = estimate_costs(ir)
        est = report.by_node["db1"]
        assert est.confidence == "low"


class TestDynamoDBEstimate:
    def test_on_demand(self) -> None:
        ir = StackMapIR(nodes=[
            _node("db1", "table", "aws_dynamodb_table",
                  {"billing_mode": "PAY_PER_REQUEST"},
                  category=ResourceCategory.DATABASE),
        ])
        report = estimate_costs(ir)
        est = report.by_node["db1"]
        assert est.monthly_estimate > 0
        assert est.pricing_model == "capacity"

    def test_provisioned(self) -> None:
        ir = StackMapIR(nodes=[
            _node("db1", "table", "aws_dynamodb_table",
                  {"billing_mode": "PROVISIONED"},
                  category=ResourceCategory.DATABASE),
        ])
        report = estimate_costs(ir)
        est = report.by_node["db1"]
        assert est.monthly_estimate > 1.25  # More than on-demand base


class TestECSEstimate:
    def test_fargate_estimate(self) -> None:
        ir = StackMapIR(nodes=[
            _node("svc1", "api-service", "aws_ecs_service",
                  {"cpu": 512, "memory": 1024, "desired_count": 2},
                  category=ResourceCategory.CONTAINER),
        ])
        report = estimate_costs(ir)
        est = report.by_node["svc1"]
        assert est.monthly_estimate > 0
        assert est.pricing_model == "fargate"


class TestGenericEstimate:
    def test_s3_bucket(self) -> None:
        ir = StackMapIR(nodes=[
            _node("s3", "bucket", "aws_s3_bucket", category=ResourceCategory.STORAGE),
        ])
        report = estimate_costs(ir)
        est = report.by_node["s3"]
        assert est.monthly_estimate > 0

    def test_nat_gateway(self) -> None:
        ir = StackMapIR(nodes=[
            _node("nat", "nat-gw", "aws_nat_gateway", category=ResourceCategory.NETWORK),
        ])
        report = estimate_costs(ir)
        est = report.by_node["nat"]
        assert est.monthly_estimate > 30

    def test_reference_types_free(self) -> None:
        ir = StackMapIR(nodes=[
            _node("vpc", "main", "aws_vpc", category=ResourceCategory.NETWORK),
            _node("sg", "web-sg", "aws_security_group", category=ResourceCategory.SECURITY),
            _node("role", "lambda-role", "aws_iam_role", category=ResourceCategory.SECURITY),
        ])
        report = estimate_costs(ir)
        for node_id in ("vpc", "sg", "role"):
            assert report.by_node[node_id].monthly_estimate == 0

    def test_unknown_resource_type(self) -> None:
        ir = StackMapIR(nodes=[
            _node("x", "mystery", "aws_mystery_service"),
        ])
        report = estimate_costs(ir)
        est = report.by_node["x"]
        assert est.confidence == "unknown"
        assert est.monthly_estimate == 0


class TestCostReport:
    def test_total_is_sum_of_nodes(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "fn", "aws_lambda_function", {"memory_size": 256}),
            _node("db1", "db", "aws_db_instance", {"instance_class": "db.t3.medium"},
                  category=ResourceCategory.DATABASE),
        ])
        report = estimate_costs(ir)
        node_sum = sum(e.monthly_estimate for e in report.by_node.values())
        assert abs(report.total_monthly - node_sum) < 0.01

    def test_by_category_aggregation(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "fn1", "aws_lambda_function", {"memory_size": 256}),
            _node("fn2", "fn2", "aws_lambda_function", {"memory_size": 512}),
        ])
        report = estimate_costs(ir)
        assert "serverless" in report.by_category
        assert report.by_category["serverless"] > 0

    def test_serialization(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "fn", "aws_lambda_function", {"memory_size": 256}),
        ])
        report = estimate_costs(ir)
        d = report.to_dict()
        assert "total_monthly" in d
        assert "by_node" in d
        assert "by_category" in d
        assert "currency" in d

    def test_expensive_paths(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("fn1", "handler", "aws_lambda_function", {"memory_size": 1024}),
                _node("db1", "prod-db", "aws_db_instance",
                      {"instance_class": "db.r6g.xlarge"},
                      category=ResourceCategory.DATABASE),
            ],
            edges=[_edge("fn1", "db1", EdgeType.WRITES_TO)],
        )
        report = estimate_costs(ir)
        assert len(report.expensive_paths) >= 1
        assert report.expensive_paths[0]["total_cost"] > 0


class TestAnnotateIR:
    def test_annotate_adds_cost_to_position_hint(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "handler", "aws_lambda_function", {"memory_size": 256}),
        ])
        annotated = annotate_ir_with_costs(ir)
        assert "cost_monthly" in annotated.nodes[0].position_hint
        assert "cost_confidence" in annotated.nodes[0].position_hint
        assert annotated.nodes[0].position_hint["cost_monthly"] > 0

    def test_annotate_adds_cost_summary_metadata(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "handler", "aws_lambda_function", {"memory_size": 256}),
        ])
        annotated = annotate_ir_with_costs(ir)
        assert "cost_summary" in annotated.metadata
        assert "total_monthly" in annotated.metadata["cost_summary"]


class TestOverrides:
    def test_lambda_usage_overrides_raise_confidence(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "handler", "aws_lambda_function", {"memory_size": 256}),
        ])

        baseline = estimate_costs(ir)
        adjusted = estimate_costs(
            ir,
            overrides={
                "fn1": {
                    "memory_mb": 512,
                    "invocations_per_month": 2_000_000,
                    "avg_duration_ms": 400,
                }
            },
        )

        assert adjusted.by_node["fn1"].monthly_estimate > baseline.by_node["fn1"].monthly_estimate
        assert adjusted.by_node["fn1"].confidence == "high"
        assert "2,000,000 invocations/month" in adjusted.by_node["fn1"].estimate_note

    def test_storage_and_transfer_overrides_adjust_costs(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("bucket", "assets", "aws_s3_bucket", category=ResourceCategory.STORAGE),
                _node("cdn", "site-cdn", "aws_cloudfront_distribution", category=ResourceCategory.CDN),
            ],
            edges=[_edge("cdn", "bucket", EdgeType.ROUTES_TO)],
        )

        baseline = estimate_costs(ir)
        adjusted = estimate_costs(
            ir,
            overrides={
                "bucket": {"storage_gb": 250},
                "cdn": {"data_transfer_gb": 1200},
            },
        )

        assert adjusted.total_monthly > baseline.total_monthly
        assert adjusted.by_node["bucket"].confidence == "high"
        assert adjusted.by_node["cdn"].confidence == "high"
        assert adjusted.expensive_paths[0]["source"] == "cdn"

    def test_serverless_aliases_resolve_to_priced_resources(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn", "handler", "AWS::Serverless::Function", {"memory_size": 256}),
        ])

        report = estimate_costs(
            ir,
            overrides={"fn": {"memory_mb": 512, "invocations_per_month": 2_000_000}},
        )

        assert report.by_node["fn"].monthly_estimate > 0
        assert report.by_node["fn"].confidence == "high"


class TestEmptyIR:
    def test_empty_ir_zero_cost(self) -> None:
        report = estimate_costs(StackMapIR())
        assert report.total_monthly == 0
        assert len(report.by_node) == 0
