"""Tests for smart grouping engine."""

import tempfile
from pathlib import Path

import yaml

from stackmap.grouping.engine import (
    AutoDetectConfig,
    GroupingRule,
    SmartGroupConfig,
    apply_smart_groups,
    auto_detect_groups,
    build_group_hierarchy,
    build_reason,
    load_grouping_config,
    score_group,
)
from stackmap.parsers.base import (
    EdgeType,
    ResourceCategory,
    StackMapEdge,
    StackMapIR,
    StackMapNode,
)


def _node(id: str, name: str, rtype: str = "aws_lambda_function",
          tags: dict | None = None, props: dict | None = None) -> StackMapNode:
    return StackMapNode(
        id=id,
        name=name,
        resource_type=rtype,
        provider="aws",
        category=ResourceCategory.SERVERLESS,
        tags=tags or {},
        properties=props or {},
    )


def _edge(src: str, tgt: str, etype: EdgeType = EdgeType.TRIGGERS) -> StackMapEdge:
    return StackMapEdge(id=f"{src}->{tgt}", source=src, target=tgt, edge_type=etype)


class TestRuleMatching:
    def test_tag_match(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "auth-handler", tags={"service": "auth"}),
            _node("fn2", "api-handler", tags={"service": "api"}),
            _node("fn3", "auth-validator", tags={"service": "auth"}),
        ])

        config = SmartGroupConfig(
            name="Auth Service",
            rules=[GroupingRule(match_type="tag", key="service", value="auth")],
        )

        result = apply_smart_groups(ir, [config])
        smart_groups = [g for g in result.groups if g.group_type == "smart_group"]
        assert len(smart_groups) == 1
        assert set(smart_groups[0].children) == {"fn1", "fn3"}

    def test_name_pattern_match(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "auth-handler"),
            _node("fn2", "auth-validator"),
            _node("fn3", "api-handler"),
        ])

        config = SmartGroupConfig(
            name="Auth",
            rules=[GroupingRule(match_type="name", pattern="auth-*")],
        )

        result = apply_smart_groups(ir, [config])
        smart_groups = [g for g in result.groups if g.group_type == "smart_group"]
        assert len(smart_groups) == 1
        assert set(smart_groups[0].children) == {"fn1", "fn2"}

    def test_resource_type_match(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "fn", "aws_lambda_function"),
            _node("db1", "db", "aws_dynamodb_table"),
            _node("fn2", "fn2", "aws_lambda_function"),
        ])

        config = SmartGroupConfig(
            name="Lambdas",
            rules=[GroupingRule(match_type="type", pattern="aws_lambda_*")],
        )

        result = apply_smart_groups(ir, [config])
        smart_groups = [g for g in result.groups if g.group_type == "smart_group"]
        assert len(smart_groups) == 1
        assert set(smart_groups[0].children) == {"fn1", "fn2"}

    def test_vpc_match(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "fn", props={"vpc_id": "vpc-abc123"}),
            _node("fn2", "fn2", props={"vpc_id": "vpc-abc123"}),
            _node("fn3", "fn3", props={"vpc_id": "vpc-other"}),
        ])

        config = SmartGroupConfig(
            name="Main VPC",
            rules=[GroupingRule(match_type="vpc", value="vpc-abc123")],
        )

        result = apply_smart_groups(ir, [config])
        smart_groups = [g for g in result.groups if g.group_type == "smart_group"]
        assert len(smart_groups) == 1
        assert set(smart_groups[0].children) == {"fn1", "fn2"}

    def test_first_match_wins(self) -> None:
        """A node should only belong to the first matching group."""
        ir = StackMapIR(nodes=[
            _node("fn1", "auth-handler", tags={"service": "auth", "team": "security"}),
        ])

        configs = [
            SmartGroupConfig(name="Auth", rules=[GroupingRule(match_type="tag", key="service", value="auth")]),
            SmartGroupConfig(name="Security", rules=[GroupingRule(match_type="tag", key="team", value="security")]),
        ]

        result = apply_smart_groups(ir, configs)
        smart_groups = [g for g in result.groups if g.group_type == "smart_group"]
        # fn1 should only be in Auth (first match)
        assert len(smart_groups) == 1
        assert smart_groups[0].name == "Auth"

    def test_no_match_no_group(self) -> None:
        ir = StackMapIR(nodes=[_node("fn1", "handler")])
        config = SmartGroupConfig(
            name="Empty",
            rules=[GroupingRule(match_type="tag", key="nonexistent", value="x")],
        )
        result = apply_smart_groups(ir, [config])
        smart_groups = [g for g in result.groups if g.group_type == "smart_group"]
        assert len(smart_groups) == 0


class TestAutoDetect:
    def test_tag_based_clustering(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "a", tags={"service": "auth"}),
            _node("fn2", "b", tags={"service": "auth"}),
            _node("fn3", "c", tags={"service": "auth"}),
            _node("fn4", "d", tags={"service": "api"}),
        ])

        config = AutoDetectConfig(tag_keys=["service"], min_group_size=3)
        groups = auto_detect_groups(ir, config)

        assert len(groups) >= 1
        auth_groups = [g for g in groups if "auth" in g.id]
        assert len(auth_groups) == 1
        assert len(auth_groups[0].children) == 3

    def test_naming_prefix_clustering(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "analytics-ingester"),
            _node("fn2", "analytics-processor"),
            _node("fn3", "analytics-writer"),
            _node("fn4", "auth-handler"),
        ])

        config = AutoDetectConfig(
            tag_keys=[], naming_prefix=True, min_group_size=3, vpc_based=False,
        )
        groups = auto_detect_groups(ir, config)

        prefix_groups = [g for g in groups if g.metadata.get("auto_strategy") == "naming_prefix"]
        assert len(prefix_groups) >= 1
        assert any("analytics" in g.id for g in prefix_groups)

    def test_connectivity_clustering(self) -> None:
        ir = StackMapIR(
            nodes=[
                _node("fn1", "handler"),
                _node("db1", "table", "aws_dynamodb_table"),
                _node("s3", "bucket", "aws_s3_bucket"),
                _node("isolated1", "lone-fn"),
                _node("isolated2", "lone-db"),
                _node("isolated3", "lone-s3"),
            ],
            edges=[
                _edge("fn1", "db1", EdgeType.WRITES_TO),
                _edge("fn1", "s3", EdgeType.WRITES_TO),
                _edge("isolated1", "isolated2", EdgeType.WRITES_TO),
                _edge("isolated2", "isolated3", EdgeType.TRIGGERS),
            ],
        )

        config = AutoDetectConfig(tag_keys=[], naming_prefix=False, vpc_based=False, min_group_size=3)
        groups = auto_detect_groups(ir, config)

        connectivity_groups = [g for g in groups if g.metadata.get("auto_strategy") == "connectivity"]
        assert len(connectivity_groups) >= 1


class TestConfigLoading:
    def test_load_yaml_config(self) -> None:
        config_data = {
            "version": 1,
            "groups": [
                {
                    "name": "Auth Service",
                    "icon": "security",
                    "color": "#ef4444",
                    "rules": [
                        {"match": "tag", "key": "service", "value": "auth"},
                        {"match": "name", "pattern": "auth-*"},
                    ],
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            path = f.name

        groups, auto_config = load_grouping_config(path)
        assert len(groups) == 1
        assert groups[0].name == "Auth Service"
        assert len(groups[0].rules) == 2
        assert groups[0].rules[0].match_type == "tag"
        assert groups[0].rules[1].pattern == "auth-*"

        Path(path).unlink()

    def test_load_missing_config(self) -> None:
        groups, auto_config = load_grouping_config("/nonexistent/path.yaml")
        assert groups == []
        assert auto_config.enabled is True


class TestSmartGroupsV2:
    def test_env_and_service_produce_hierarchy(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn.pay1", "pay-api", tags={"env": "prod", "service": "payments"}),
            _node("fn.pay2", "pay-worker", tags={"env": "prod", "service": "payments"}),
            _node("fn.pay3", "pay-callback", tags={"env": "prod", "service": "payments"}),
            _node("fn.ship1", "ship-api", tags={"env": "prod", "service": "shipping"}),
            _node("fn.ship2", "ship-worker", tags={"env": "prod", "service": "shipping"}),
            _node("fn.ship3", "ship-poller", tags={"env": "prod", "service": "shipping"}),
        ])
        groups = auto_detect_groups(ir)
        strategies = {g.metadata.get("auto_strategy") for g in groups}
        assert "environment" in strategies
        assert "tag" in strategies
        env_group = next(g for g in groups if g.metadata.get("auto_strategy") == "environment")
        service_groups = [g for g in groups if g.metadata.get("auto_strategy") == "tag"]
        # Hierarchy links service groups to the env group.
        assert all(g.parent == env_group.id for g in service_groups)
        # Reason is populated and non-empty.
        assert all(g.metadata.get("reason") for g in groups)
        # Confidence is computed and bounded.
        for g in groups:
            c = g.metadata.get("confidence")
            assert isinstance(c, float)
            assert 0.0 <= c <= 1.0

    def test_module_path_strategy(self) -> None:
        ir = StackMapIR(nodes=[
            StackMapNode(
                id=f"fn.{i}", name=f"worker-{i}",
                resource_type="aws_lambda_function", provider="aws",
                category=ResourceCategory.SERVERLESS,
                metadata={"source_module": "module.payments"},
            ) for i in range(4)
        ])
        groups = auto_detect_groups(ir)
        assert any(g.metadata.get("auto_strategy") == "module_path" for g in groups)

    def test_region_parent_only_when_multiregion(self) -> None:
        single = StackMapIR(nodes=[
            StackMapNode(id=f"fn.{i}", name=f"f{i}", resource_type="aws_lambda_function",
                         provider="aws", category=ResourceCategory.SERVERLESS,
                         tags={"service": "auth"},
                         metadata={"region": "us-east-1"}) for i in range(3)
        ])
        groups = auto_detect_groups(single)
        assert not any(g.metadata.get("auto_strategy") == "region" for g in groups)

        multi = StackMapIR(nodes=[
            StackMapNode(id="fn.a", name="a", resource_type="aws_lambda_function",
                         provider="aws", category=ResourceCategory.SERVERLESS,
                         metadata={"region": "us-east-1"}),
            StackMapNode(id="fn.b", name="b", resource_type="aws_lambda_function",
                         provider="aws", category=ResourceCategory.SERVERLESS,
                         metadata={"region": "us-east-1"}),
            StackMapNode(id="fn.c", name="c", resource_type="aws_lambda_function",
                         provider="aws", category=ResourceCategory.SERVERLESS,
                         metadata={"region": "eu-west-1"}),
            StackMapNode(id="fn.d", name="d", resource_type="aws_lambda_function",
                         provider="aws", category=ResourceCategory.SERVERLESS,
                         metadata={"region": "eu-west-1"}),
        ])
        groups = auto_detect_groups(multi)
        assert any(g.metadata.get("auto_strategy") == "region" for g in groups)

    def test_multiregion_multiaccount_roots(self) -> None:
        ir = StackMapIR(nodes=[
            StackMapNode(id=f"fn.{account}.{region}.{i}", name=f"f-{account}-{region}-{i}",
                         resource_type="aws_lambda_function", provider="aws",
                         category=ResourceCategory.SERVERLESS,
                         metadata={"account_id": account, "region": region})
            for account in ("111111111111", "222222222222")
            for region in ("us-east-1", "eu-west-1")
            for i in range(2)
        ])

        groups = auto_detect_groups(ir)

        assert sum(1 for g in groups if g.metadata.get("auto_strategy") == "account") == 2
        assert sum(1 for g in groups if g.metadata.get("auto_strategy") == "region") == 2

    def test_scoring_reason_and_hierarchy_helpers(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "auth-api", tags={"env": "prod", "service": "auth"}),
            _node("fn2", "auth-worker", tags={"env": "prod", "service": "auth"}),
            _node("fn3", "auth-hook", tags={"env": "prod", "service": "auth"}),
        ])
        groups = auto_detect_groups(ir)
        group = next(g for g in groups if g.metadata.get("auto_strategy") == "tag")

        assert score_group(group, ir) > 0
        assert "resources" in build_reason(group, ir)
        assert build_group_hierarchy(groups) is groups

    def test_shared_role_groups_compute(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn.a", "a", props={"role_arn": "arn:aws:iam::1:role/shared"}),
            _node("fn.b", "b", props={"role_arn": "arn:aws:iam::1:role/shared"}),
        ])
        groups = auto_detect_groups(ir)
        assert any(g.metadata.get("auto_strategy") == "shared_role" for g in groups)

    def test_explicit_groups_annotated_with_confidence_one(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "auth-handler", tags={"service": "auth"}),
            _node("fn2", "auth-validator", tags={"service": "auth"}),
        ])
        config = SmartGroupConfig(
            name="Auth",
            rules=[GroupingRule(match_type="tag", key="service", value="auth")],
        )
        new_ir = apply_smart_groups(ir, [config])
        assert len(new_ir.groups) == 1
        g = new_ir.groups[0]
        assert g.metadata["confidence"] == 1.0
        assert "explicit" in g.metadata["reason"].lower() or "rule" in g.metadata["reason"].lower()
