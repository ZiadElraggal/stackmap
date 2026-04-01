from __future__ import annotations

import json
from pathlib import Path

import boto3
import pytest
from botocore.stub import Stubber

from stackmap.aws_live.scanner import (
    AWSAPIExecutor,
    AWSLiveScanner,
    APIRecorder,
    AccountScanContext,
    build_policy_document,
)
from stackmap.parsers.base import EdgeType


class _FakeCreds:
    method = "shared-credentials-file"


class _FakeSTSClient:
    def __init__(self, account_id: str) -> None:
        self._account_id = account_id

    def get_caller_identity(self) -> dict[str, str]:
        return {"Account": self._account_id}

    def assume_role(self, **_: object) -> dict[str, dict[str, str]]:
        return {
            "Credentials": {
                "AccessKeyId": "test",
                "SecretAccessKey": "test",
                "SessionToken": "test",
            }
        }


class _FakeSession:
    def __init__(self, account_id: str = "123456789012", region_name: str = "us-east-1") -> None:
        self.account_id = account_id
        self.region_name = region_name

    def get_credentials(self) -> _FakeCreds:
        return _FakeCreds()

    def client(self, service: str, **_: object) -> _FakeSTSClient:
        if service != "sts":
            raise AssertionError(f"Unexpected client request: {service}")
        return _FakeSTSClient(self.account_id)

    def get_available_regions(self, _service: str) -> list[str]:
        return [self.region_name]


def test_build_policy_document_broad_includes_extended_actions() -> None:
    core = build_policy_document("core")
    broad = build_policy_document("broad")

    assert "ec2:Describe*" in core["Statement"][0]["Action"]
    assert "config:ListDiscoveredResources" not in core["Statement"][0]["Action"]
    assert "config:ListDiscoveredResources" in broad["Statement"][0]["Action"]


def test_dry_run_plan_single_account_records_expected_calls() -> None:
    scanner = AWSLiveScanner(
        profile="sandbox",
        regions=["us-east-1"],
        services={"ec2", "lambda"},
        dry_run=True,
        session_factory=lambda **_: _FakeSession(),
    )

    plan = scanner.dry_run_plan()

    calls = {(call.service, call.operation) for call in plan}
    assert ("ec2", "describe_vpcs") in calls
    assert ("lambda", "list_functions") in calls
    assert ("lambda", "list_event_source_mappings") in calls


def test_collect_lambda_with_stubber_creates_nodes_and_pending_edges(tmp_path: Path) -> None:
    session = boto3.session.Session(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
    lambda_client = session.client("lambda", region_name="us-east-1")
    stubber = Stubber(lambda_client)
    stubber.add_response(
        "list_functions",
        {
            "Functions": [
                {
                    "FunctionName": "orders-handler",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:orders-handler",
                    "Runtime": "python3.12",
                    "Handler": "handler.main",
                    "Role": "arn:aws:iam::123456789012:role/orders-role",
                    "MemorySize": 512,
                    "Timeout": 30,
                    "VpcConfig": {
                        "VpcId": "vpc-1234",
                        "SubnetIds": ["subnet-a"],
                        "SecurityGroupIds": ["sg-1"],
                    },
                    "Environment": {
                        "Variables": {
                            "QUEUE_ARN": "arn:aws:sqs:us-east-1:123456789012:orders"
                        }
                    },
                    "LastModified": "2026-03-31T00:00:00.000+0000",
                }
            ]
        },
    )
    stubber.add_response(
        "list_event_source_mappings",
        {
            "EventSourceMappings": [
                {
                    "UUID": "uuid-1",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:orders-handler",
                    "EventSourceArn": "arn:aws:sqs:us-east-1:123456789012:orders",
                }
            ]
        },
    )
    stubber.activate()

    class _Session:
        def client(self, service: str, **_: object):  # type: ignore[no-untyped-def]
            if service != "lambda":
                raise AssertionError(f"Unexpected service: {service}")
            return lambda_client

        region_name = "us-east-1"

    context = AccountScanContext(
        session=_Session(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name=None,
        auth_description="test",
        role_arn=None,
        services={"lambda"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )

    scanner = AWSLiveScanner(regions=["us-east-1"], services={"lambda"})
    nodes, pending, groups = scanner._collect_lambda("us-east-1", AWSAPIExecutor(context))

    assert len(nodes) == 1
    assert groups == []
    assert nodes[0].resource_type == "aws_lambda_function"
    assert nodes[0].metadata["source_type"] == "aws_live"
    assert any(edge[2] == "assumes role" and edge[3] == EdgeType.AUTHENTICATES for edge in pending)
    assert any(edge[2] == "reads from" and edge[3] == EdgeType.READS_FROM for edge in pending)
    assert any(edge[2] == "references" and "orders" in str(edge[1]) for edge in pending)

    stubber.deactivate()


def test_paginated_access_denied_becomes_warning(tmp_path: Path) -> None:
    session = boto3.session.Session(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
    lambda_client = session.client("lambda", region_name="us-east-1")
    stubber = Stubber(lambda_client)
    stubber.add_client_error("list_functions", service_error_code="AccessDeniedException")
    stubber.activate()

    class _Session:
        def client(self, service: str, **_: object):  # type: ignore[no-untyped-def]
            if service != "lambda":
                raise AssertionError(f"Unexpected service: {service}")
            return lambda_client

        region_name = "us-east-1"

    context = AccountScanContext(
        session=_Session(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name=None,
        auth_description="test",
        role_arn=None,
        services={"lambda"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )

    executor = AWSAPIExecutor(context)
    values = executor.paginate("lambda", "list_functions", "Functions", region="us-east-1")

    assert values == []
    assert any("denied" in warning for warning in context.warnings)

    stubber.deactivate()


def test_build_ir_creates_explicit_edges_and_live_metadata() -> None:
    scanner = AWSLiveScanner(regions=["us-east-1"], services={"lambda", "iam"})
    context = AccountScanContext(
        session=_FakeSession(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name="prod",
        auth_description="profile 'sandbox'",
        role_arn=None,
        services={"lambda", "iam"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=None,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )

    from stackmap.parsers.base import ResourceCategory, StackMapNode

    lambda_node = StackMapNode(
        id="aws:123456789012:us-east-1:aws_lambda_function:orders-handler",
        name="orders-handler",
        resource_type="aws_lambda_function",
        provider="aws",
        category=ResourceCategory.SERVERLESS,
        properties={
            "id": "orders-handler",
            "arn": "arn:aws:lambda:us-east-1:123456789012:function:orders-handler",
            "function_name": "orders-handler",
        },
        metadata={"account_id": "123456789012", "region": "us-east-1", "source_type": "aws_live"},
        position_hint={"tier": "backend"},
    )
    role_node = StackMapNode(
        id="aws:123456789012:global:aws_iam_role:orders-role",
        name="orders-role",
        resource_type="aws_iam_role",
        provider="aws",
        category=ResourceCategory.SECURITY,
        properties={
            "id": "orders-role",
            "arn": "arn:aws:iam::123456789012:role/orders-role",
        },
        metadata={"account_id": "123456789012", "region": "global", "source_type": "aws_live"},
        position_hint={"tier": "backend"},
    )

    ir = scanner._build_ir(
        context,
        [lambda_node, role_node],
        [(lambda_node.id, "arn:aws:iam::123456789012:role/orders-role", "assumes role", EdgeType.AUTHENTICATES)],
        [],
    )

    assert ir.metadata["source_type"] == "aws_live"
    assert ir.metadata["source_kind"] == "live_scan"
    assert len(ir.edges) == 1
    assert ir.edges[0].target == role_node.id
