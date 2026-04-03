from __future__ import annotations

import json
from datetime import UTC, datetime
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
from stackmap.organizations import OrganizationDocument
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


def test_build_ir_resolves_direct_node_id_references() -> None:
    from stackmap.parsers.base import ResourceCategory, StackMapNode

    scanner = AWSLiveScanner(regions=["us-east-1"], services={"ec2"})
    context = AccountScanContext(
        session=_FakeSession(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name="prod",
        auth_description="profile 'sandbox'",
        role_arn=None,
        services={"ec2"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=None,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )
    vpc_node = StackMapNode(
        id="aws:123456789012:us-east-1:aws_vpc:vpc-1234",
        name="main",
        resource_type="aws_vpc",
        provider="aws",
        category=ResourceCategory.NETWORK,
        properties={"id": "vpc-1234", "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-1234"},
        metadata={"account_id": "123456789012", "region": "us-east-1"},
        position_hint={"tier": "frontend"},
    )
    subnet_node = StackMapNode(
        id="aws:123456789012:us-east-1:aws_subnet:subnet-a",
        name="subnet-a",
        resource_type="aws_subnet",
        provider="aws",
        category=ResourceCategory.NETWORK,
        properties={"id": "subnet-a", "arn": "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-a", "vpc_id": "vpc-1234"},
        metadata={"account_id": "123456789012", "region": "us-east-1"},
        position_hint={"tier": "frontend"},
    )

    ir = scanner._build_ir(
        context,
        [vpc_node, subnet_node],
        [(subnet_node.id, vpc_node.id, "in vpc", EdgeType.REFERENCES)],
        [],
    )

    assert len(ir.edges) == 1
    assert ir.edges[0].target == vpc_node.id


def test_dry_run_org_scan_can_auto_discover_without_org_file(monkeypatch) -> None:
    scanner = AWSLiveScanner(
        profile="sandbox",
        regions=["us-east-1"],
        services={"ec2"},
        dry_run=True,
        org_scan=True,
        session_factory=lambda **_: _FakeSession(),
    )

    monkeypatch.setattr(
        scanner,
        "_load_or_discover_org",
        lambda _session: OrganizationDocument(
            org_id="o-test",
            root_id="r-root",
            root_name="Root",
            ous=[],
            accounts=[{"id": "210000000001", "name": "prod", "parent": "r-root", "ou_path": "Root"}],
        ),
    )

    plan = scanner.dry_run_plan()
    assert len(plan) > 0
    assert all(call.account_id == "210000000001" for call in plan)


def test_collect_s3_keeps_bucket_when_optional_calls_fail(tmp_path: Path) -> None:
    session = boto3.session.Session(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
    s3_client = session.client("s3", region_name="us-east-1")
    stubber = Stubber(s3_client)
    stubber.add_response(
        "list_buckets",
        {"Buckets": [{"Name": "stackmap-bucket", "CreationDate": datetime(2026, 3, 31, tzinfo=UTC)}]},
    )
    stubber.add_response("get_bucket_location", {}, {"Bucket": "stackmap-bucket"})
    stubber.add_client_error("get_bucket_tagging", service_error_code="NoSuchTagSet", expected_params={"Bucket": "stackmap-bucket"})
    stubber.add_client_error("get_bucket_policy", service_error_code="NoSuchBucketPolicy", expected_params={"Bucket": "stackmap-bucket"})
    stubber.activate()

    class _Session:
        def client(self, service: str, **_: object):  # type: ignore[no-untyped-def]
            if service != "s3":
                raise AssertionError(f"Unexpected service: {service}")
            return s3_client

        region_name = "us-east-1"

    context = AccountScanContext(
        session=_Session(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name=None,
        auth_description="test",
        role_arn=None,
        services={"s3"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )
    scanner = AWSLiveScanner(regions=["us-east-1"], services={"s3"})
    nodes, pending, groups = scanner._collect_s3("us-east-1", AWSAPIExecutor(context))

    assert len(nodes) == 1
    assert nodes[0].resource_type == "aws_s3_bucket"
    assert pending == []
    assert groups == []

    stubber.deactivate()


def test_collect_s3_collects_all_buckets_regardless_of_region(tmp_path: Path) -> None:
    """S3 is global: buckets in all regions should be collected, not just the scan region."""
    session = boto3.session.Session(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
    s3_client = session.client("s3", region_name="us-east-1")
    stubber = Stubber(s3_client)
    stubber.add_response(
        "list_buckets",
        {
            "Buckets": [
                {"Name": "us-bucket", "CreationDate": datetime(2026, 3, 31, tzinfo=UTC)},
                {"Name": "eu-bucket", "CreationDate": datetime(2026, 3, 31, tzinfo=UTC)},
            ]
        },
    )
    # us-bucket in us-east-1 (empty LocationConstraint -> us-east-1)
    stubber.add_response("get_bucket_location", {}, {"Bucket": "us-bucket"})
    stubber.add_client_error("get_bucket_tagging", service_error_code="NoSuchTagSet", expected_params={"Bucket": "us-bucket"})
    stubber.add_client_error("get_bucket_policy", service_error_code="NoSuchBucketPolicy", expected_params={"Bucket": "us-bucket"})
    # eu-bucket in eu-west-1
    stubber.add_response("get_bucket_location", {"LocationConstraint": "eu-west-1"}, {"Bucket": "eu-bucket"})
    stubber.add_client_error("get_bucket_tagging", service_error_code="NoSuchTagSet", expected_params={"Bucket": "eu-bucket"})
    stubber.add_client_error("get_bucket_policy", service_error_code="NoSuchBucketPolicy", expected_params={"Bucket": "eu-bucket"})
    stubber.activate()

    class _Session:
        def client(self, service: str, **_: object):  # type: ignore[no-untyped-def]
            if service != "s3":
                raise AssertionError(f"Unexpected service: {service}")
            return s3_client

        region_name = "us-east-1"

    context = AccountScanContext(
        session=_Session(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name=None,
        auth_description="test",
        role_arn=None,
        services={"s3"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )
    scanner = AWSLiveScanner(regions=["us-east-1"], services={"s3"})
    nodes, pending, groups = scanner._collect_s3("us-east-1", AWSAPIExecutor(context))

    assert len(nodes) == 2
    bucket_names = {n.name for n in nodes}
    assert "us-bucket" in bucket_names
    assert "eu-bucket" in bucket_names
    # eu-bucket should have eu-west-1 in its metadata, not us-east-1
    eu_node = next(n for n in nodes if n.name == "eu-bucket")
    assert eu_node.metadata["region"] == "eu-west-1"

    stubber.deactivate()


def test_build_ir_suppresses_vpc_groups_with_only_infra_children() -> None:
    """VPC groups that only contain subnets/SGs but no workloads should be filtered out."""
    from stackmap.parsers.base import ResourceCategory, StackMapGroup, StackMapNode

    scanner = AWSLiveScanner(regions=["us-east-1"], services={"ec2"})
    context = AccountScanContext(
        session=_FakeSession(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name="prod",
        auth_description="test",
        role_arn=None,
        services={"ec2"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=None,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )
    vpc_node = StackMapNode(
        id="aws:123456789012:us-east-1:aws_vpc:vpc-empty",
        name="default",
        resource_type="aws_vpc",
        provider="aws",
        category=ResourceCategory.NETWORK,
        properties={"id": "vpc-empty", "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-empty"},
        metadata={"account_id": "123456789012", "region": "us-east-1"},
        position_hint={"tier": "frontend"},
    )
    sg_node = StackMapNode(
        id="aws:123456789012:us-east-1:aws_security_group:sg-1",
        name="default",
        resource_type="aws_security_group",
        provider="aws",
        category=ResourceCategory.SECURITY,
        properties={"id": "sg-1", "vpc_id": "vpc-empty"},
        metadata={"account_id": "123456789012", "region": "us-east-1"},
        position_hint={"tier": "frontend"},
    )
    vpc_group = StackMapGroup(
        id="group:vpc:123456789012:us-east-1:vpc-empty",
        name="default",
        group_type="vpc",
        children=[],
    )

    ir = scanner._build_ir(context, [vpc_node, sg_node], [], [vpc_group])

    # VPC group should be suppressed because it only has a security group (infra), no workloads
    vpc_groups = [g for g in ir.groups if g.group_type == "vpc"]
    assert len(vpc_groups) == 0


def test_build_ir_keeps_vpc_groups_with_workload_children() -> None:
    """VPC groups that contain actual workloads (e.g. Lambda, RDS) should be kept."""
    from stackmap.parsers.base import ResourceCategory, StackMapGroup, StackMapNode

    scanner = AWSLiveScanner(regions=["us-east-1"], services={"ec2", "lambda"})
    context = AccountScanContext(
        session=_FakeSession(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name="prod",
        auth_description="test",
        role_arn=None,
        services={"ec2", "lambda"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=None,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )
    vpc_node = StackMapNode(
        id="aws:123456789012:us-east-1:aws_vpc:vpc-active",
        name="prod-vpc",
        resource_type="aws_vpc",
        provider="aws",
        category=ResourceCategory.NETWORK,
        properties={"id": "vpc-active", "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-active"},
        metadata={"account_id": "123456789012", "region": "us-east-1"},
        position_hint={"tier": "frontend"},
    )
    lambda_node = StackMapNode(
        id="aws:123456789012:us-east-1:aws_lambda_function:my-fn",
        name="my-fn",
        resource_type="aws_lambda_function",
        provider="aws",
        category=ResourceCategory.SERVERLESS,
        properties={"id": "my-fn", "vpc_id": "vpc-active"},
        metadata={"account_id": "123456789012", "region": "us-east-1"},
        position_hint={"tier": "backend"},
    )
    vpc_group = StackMapGroup(
        id="group:vpc:123456789012:us-east-1:vpc-active",
        name="prod-vpc",
        group_type="vpc",
        children=[],
    )

    ir = scanner._build_ir(context, [vpc_node, lambda_node], [], [vpc_group])

    vpc_groups = [g for g in ir.groups if g.group_type == "vpc"]
    assert len(vpc_groups) == 1
    assert lambda_node.id in vpc_groups[0].children


def test_org_setup_template_structure() -> None:
    """Verify the CloudFormation template has the expected structure."""
    from stackmap.aws_live.org_setup import build_stackmap_role_template

    template = build_stackmap_role_template(
        role_name="StackMapReadOnly",
        management_account_id="111111111111",
        service_set="core",
    )

    assert template["AWSTemplateFormatVersion"] == "2010-09-09"
    role = template["Resources"]["StackMapReadOnlyRole"]
    assert role["Type"] == "AWS::IAM::Role"
    trust = role["Properties"]["AssumeRolePolicyDocument"]
    assert trust["Statement"][0]["Principal"]["AWS"] == "arn:aws:iam::111111111111:root"
    assert trust["Statement"][0]["Action"] == "sts:AssumeRole"
    policy_actions = role["Properties"]["Policies"][0]["PolicyDocument"]["Statement"][0]["Action"]
    assert "ec2:Describe*" in policy_actions
    # core set should not include config
    assert "config:ListDiscoveredResources" not in policy_actions


def test_org_setup_template_with_external_id() -> None:
    from stackmap.aws_live.org_setup import build_stackmap_role_template

    template = build_stackmap_role_template(
        role_name="StackMapReadOnly",
        management_account_id="111111111111",
        external_id="my-secret-id",
    )

    trust = template["Resources"]["StackMapReadOnlyRole"]["Properties"]["AssumeRolePolicyDocument"]
    condition = trust["Statement"][0]["Condition"]
    assert condition["StringEquals"]["sts:ExternalId"] == "my-secret-id"


def test_collect_cognito_creates_user_pool_nodes_and_trigger_edges(tmp_path: Path) -> None:
    """Cognito collector should discover user pools, clients, and Lambda trigger edges."""
    session = boto3.session.Session(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
    idp_client = session.client("cognito-idp", region_name="us-east-1")
    identity_client = session.client("cognito-identity", region_name="us-east-1")
    idp_stubber = Stubber(idp_client)
    identity_stubber = Stubber(identity_client)

    idp_stubber.add_response(
        "list_user_pools",
        {
            "UserPools": [
                {"Id": "us-east-1_POOL1", "Name": "auth-pool", "CreationDate": datetime(2026, 1, 1, tzinfo=UTC)},
            ]
        },
        {"MaxResults": 60},
    )
    idp_stubber.add_response(
        "describe_user_pool",
        {
            "UserPool": {
                "Id": "us-east-1_POOL1",
                "Name": "auth-pool",
                "Arn": "arn:aws:cognito-idp:us-east-1:123456789012:userpool/us-east-1_POOL1",
                "Status": "Enabled",
                "LambdaConfig": {
                    "PreSignUp": "arn:aws:lambda:us-east-1:123456789012:function:pre-signup",
                },
            }
        },
        {"UserPoolId": "us-east-1_POOL1"},
    )
    idp_stubber.add_response(
        "list_user_pool_clients",
        {
            "UserPoolClients": [
                {"ClientId": "abc123", "ClientName": "web-app", "UserPoolId": "us-east-1_POOL1"},
            ]
        },
        {"UserPoolId": "us-east-1_POOL1", "MaxResults": 60},
    )
    idp_stubber.add_response(
        "describe_user_pool_client",
        {
            "UserPoolClient": {
                "ClientId": "abc123",
                "ClientName": "web-app",
                "UserPoolId": "us-east-1_POOL1",
                "AllowedOAuthFlows": ["code"],
                "CallbackURLs": ["https://app.example.com/callback"],
            }
        },
        {"UserPoolId": "us-east-1_POOL1", "ClientId": "abc123"},
    )
    identity_stubber.add_response(
        "list_identity_pools",
        {"IdentityPools": []},
        {"MaxResults": 60},
    )

    idp_stubber.activate()
    identity_stubber.activate()

    class _Session:
        def client(self, service: str, **_: object):  # type: ignore[no-untyped-def]
            if service == "cognito-idp":
                return idp_client
            if service == "cognito-identity":
                return identity_client
            raise AssertionError(f"Unexpected service: {service}")

        region_name = "us-east-1"

    context = AccountScanContext(
        session=_Session(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name=None,
        auth_description="test",
        role_arn=None,
        services={"cognito"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )

    scanner = AWSLiveScanner(regions=["us-east-1"], services={"cognito"})
    nodes, pending, groups = scanner._collect_cognito("us-east-1", AWSAPIExecutor(context))

    assert len(nodes) == 2  # user pool + client
    pool_nodes = [n for n in nodes if n.resource_type == "aws_cognito_user_pool"]
    client_nodes = [n for n in nodes if n.resource_type == "aws_cognito_user_pool_client"]
    assert len(pool_nodes) == 1
    assert len(client_nodes) == 1
    assert pool_nodes[0].name == "auth-pool"
    assert client_nodes[0].name == "web-app"
    # Should have a trigger edge to the PreSignUp Lambda
    trigger_edges = [e for e in pending if "trigger" in e[2]]
    assert len(trigger_edges) == 1
    assert "pre-signup" in trigger_edges[0][1]

    idp_stubber.deactivate()
    identity_stubber.deactivate()


def test_collect_stepfunctions_creates_nodes_with_role_edges(tmp_path: Path) -> None:
    """Step Functions collector should discover state machines and link to IAM roles."""
    session = boto3.session.Session(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
    sfn_client = session.client("stepfunctions", region_name="us-east-1")
    stubber = Stubber(sfn_client)

    stubber.add_response(
        "list_state_machines",
        {
            "stateMachines": [
                {
                    "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:order-workflow",
                    "name": "order-workflow",
                    "type": "STANDARD",
                    "creationDate": datetime(2026, 1, 1, tzinfo=UTC),
                },
            ]
        },
    )
    stubber.add_response(
        "describe_state_machine",
        {
            "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:order-workflow",
            "name": "order-workflow",
            "type": "STANDARD",
            "status": "ACTIVE",
            "roleArn": "arn:aws:iam::123456789012:role/sfn-role",
            "definition": '{"StartAt":"Process","States":{"Process":{"Type":"Task","Resource":"arn:aws:lambda:us-east-1:123456789012:function:process-order","End":true}}}',
            "creationDate": datetime(2026, 1, 1, tzinfo=UTC),
        },
        {"stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:order-workflow"},
    )
    stubber.activate()

    class _Session:
        def client(self, service: str, **_: object):  # type: ignore[no-untyped-def]
            if service != "stepfunctions":
                raise AssertionError(f"Unexpected service: {service}")
            return sfn_client

        region_name = "us-east-1"

    context = AccountScanContext(
        session=_Session(),  # type: ignore[arg-type]
        account_id="123456789012",
        account_name=None,
        auth_description="test",
        role_arn=None,
        services={"stepfunctions"},
        regions=["us-east-1"],
        recorder=APIRecorder(),
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        dry_run=False,
        verbose=False,
    )

    scanner = AWSLiveScanner(regions=["us-east-1"], services={"stepfunctions"})
    nodes, pending, groups = scanner._collect_stepfunctions("us-east-1", AWSAPIExecutor(context))

    assert len(nodes) == 1
    assert nodes[0].resource_type == "aws_sfn_state_machine"
    assert nodes[0].name == "order-workflow"
    # Should have edges: assumes role + invokes lambda
    role_edges = [e for e in pending if "assumes role" in e[2]]
    invoke_edges = [e for e in pending if "invokes" in e[2]]
    assert len(role_edges) == 1
    assert len(invoke_edges) >= 1
    assert "process-order" in invoke_edges[0][1]

    stubber.deactivate()


def test_new_services_in_broad_set() -> None:
    """Verify new services are included in the broad service set."""
    from stackmap.aws_live.scanner import SERVICE_SET_BROAD

    assert "cognito" in SERVICE_SET_BROAD
    assert "stepfunctions" in SERVICE_SET_BROAD
    assert "ecr" in SERVICE_SET_BROAD
    assert "appsync" in SERVICE_SET_BROAD


def test_broad_policy_includes_new_service_actions() -> None:
    """Verify broad policy includes actions for new services."""
    broad = build_policy_document("broad")
    actions = broad["Statement"][0]["Action"]
    assert "cognito-idp:ListUserPools" in actions
    assert "states:ListStateMachines" in actions
    assert "ecr:DescribeRepositories" in actions
    assert "appsync:ListGraphqlApis" in actions
