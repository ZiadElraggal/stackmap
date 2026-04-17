"""Read-only live AWS account scanning."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from stackmap.organizations import (
    OrganizationDocument,
    build_org_document_from_session,
    infer_cross_account_edges,
    load_organization_document,
    overlay_organization_groups,
)
from stackmap.parsers.base import (
    EdgeType,
    ResourceCategory,
    StackMapEdge,
    StackMapGroup,
    StackMapIR,
    StackMapNode,
)
from stackmap.parsers.terraform import RESOURCE_CATEGORY_MAP, TIER_MAP, WEIGHT_MAP

ServiceName = str

SERVICE_SET_CORE: tuple[ServiceName, ...] = (
    "ec2",
    "elbv2",
    "lambda",
    "apigateway",
    "ecs",
    "rds",
    "dynamodb",
    "s3",
    "cloudfront",
    "route53",
    "sqs",
    "sns",
    "iam",
)
SERVICE_SET_BROAD: tuple[ServiceName, ...] = SERVICE_SET_CORE + (
    "elasticache",
    "secretsmanager",
    "eventbridge",
    "cognito",
    "stepfunctions",
    "ecr",
    "appsync",
    "tagging",
    "config",
)
GLOBAL_SERVICES = {"iam", "s3", "cloudfront", "route53"}
DEFAULT_CACHE_TTL_SECONDS = 3600

POLICY_ACTIONS_CORE = [
    "ec2:Describe*",
    "lambda:List*",
    "lambda:GetFunction",
    "lambda:GetPolicy",
    "rds:Describe*",
    "s3:ListAllMyBuckets",
    "s3:GetBucketLocation",
    "s3:GetBucketTagging",
    "s3:GetBucketPolicy",
    "ecs:List*",
    "ecs:Describe*",
    "sqs:ListQueues",
    "sqs:GetQueueAttributes",
    "sns:ListTopics",
    "sns:GetTopicAttributes",
    "cloudfront:ListDistributions",
    "route53:ListHostedZones",
    "route53:ListResourceRecordSets",
    "apigateway:GET",
    "elasticloadbalancing:Describe*",
    "dynamodb:ListTables",
    "dynamodb:DescribeTable",
    "iam:ListRoles",
    "iam:GetRole",
    "iam:ListRolePolicies",
    "iam:GetRolePolicy",
    "iam:ListAttachedRolePolicies",
    "iam:GetPolicy",
    "iam:GetPolicyVersion",
]
POLICY_ACTIONS_BROAD = POLICY_ACTIONS_CORE + [
    "elasticache:Describe*",
    "secretsmanager:ListSecrets",
    "events:ListRules",
    "events:ListTargetsByRule",
    "cognito-idp:ListUserPools",
    "cognito-idp:DescribeUserPool",
    "cognito-idp:ListUserPoolClients",
    "cognito-idp:DescribeUserPoolClient",
    "cognito-identity:ListIdentityPools",
    "cognito-identity:DescribeIdentityPool",
    "states:ListStateMachines",
    "states:DescribeStateMachine",
    "states:ListExecutions",
    "ecr:DescribeRepositories",
    "ecr:ListTagsForResource",
    "appsync:ListGraphqlApis",
    "appsync:ListDataSources",
    "tag:GetResources",
    "config:ListDiscoveredResources",
    "config:BatchGetResourceConfig",
]

# Optional permissions for billing integration and live logs.
# These are NOT included in the default scan policy. They are exposed as
# standalone add-on policies so users can review and attach only what they need.
POLICY_ACTIONS_BILLING = [
    "ce:GetCostAndUsage",
    "cloudwatch:GetMetricStatistics",
]
POLICY_ACTIONS_LOGS = [
    "logs:DescribeLogGroups",
    "logs:FilterLogEvents",
    "logs:GetLogEvents",
]

POLICY_ACTIONS_OPTIONAL = {
    "billing": POLICY_ACTIONS_BILLING,
    "logs": POLICY_ACTIONS_LOGS,
}

_LIVE_WRITE_ACTIONS = {
    "PutItem", "UpdateItem", "DeleteItem", "BatchWriteItem", "PutObject",
    "DeleteObject", "SendMessage", "Publish", "StartExecution",
    "PutEvents", "UpdateSecret", "PutSecretValue",
}
_LIVE_READ_ACTIONS = {
    "GetItem", "Query", "Scan", "BatchGetItem", "GetObject", "ListBucket",
    "ReceiveMessage", "GetQueueAttributes", "GetSecretValue", "DescribeSecret",
}
_LIVE_INVOKE_ACTIONS = {"InvokeFunction", "Invoke", "StartExecution"}
_FUNCTIONAL_EDGE_TYPES = {
    EdgeType.TRIGGERS,
    EdgeType.ROUTES_TO,
    EdgeType.READS_FROM,
    EdgeType.WRITES_TO,
    EdgeType.CROSS_ACCOUNT_REFERENCE,
}


def build_policy_document(
    service_set: str = "broad",
    extras: list[str] | None = None,
) -> dict[str, Any]:
    """Build an IAM policy document for StackMap.

    Args:
        service_set: "core" or "broad" base permission set.
        extras: Optional list of extra permission sets to include.
            Supported: "billing" (Cost Explorer + CloudWatch metrics),
                       "logs" (CloudWatch Logs viewer).
    """
    actions = list(POLICY_ACTIONS_CORE if service_set == "core" else POLICY_ACTIONS_BROAD)
    extras = extras or []
    for extra in extras:
        if extra == "billing":
            actions.extend(POLICY_ACTIONS_BILLING)
        elif extra == "logs":
            actions.extend(POLICY_ACTIONS_LOGS)
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "StackMapReadOnly",
                "Effect": "Allow",
                "Action": actions,
                "Resource": "*",
            }
        ],
    }


def build_addon_policy_document(addon: str) -> dict[str, Any]:
    """Build a standalone IAM policy document for an optional live feature."""
    normalized = addon.lower()
    actions = POLICY_ACTIONS_OPTIONAL.get(normalized)
    if actions is None:
        raise ValueError(f"Unknown add-on policy: {addon}")

    sid = {
        "billing": "StackMapBillingReadOnly",
        "logs": "StackMapLiveLogsReadOnly",
    }[normalized]

    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": sid,
                "Effect": "Allow",
                "Action": actions,
                "Resource": "*",
            }
        ],
    }


@dataclass
class PlannedAPICall:
    account_id: str
    region: str
    service: str
    operation: str
    params: dict[str, Any]


@dataclass
class APIRecorder:
    dry_run: bool = False
    verbose: bool = False
    planned: list[PlannedAPICall] = field(default_factory=list)
    actual_count: int = 0

    def plan(self, account_id: str, region: str, service: str, operation: str, params: dict[str, Any]) -> None:
        self.planned.append(
            PlannedAPICall(
                account_id=account_id,
                region=region,
                service=service,
                operation=operation,
                params=params,
            )
        )

    def executed(self) -> None:
        self.actual_count += 1


@dataclass
class AccountScanContext:
    session: boto3.session.Session
    account_id: str
    account_name: str | None
    auth_description: str
    role_arn: str | None
    services: set[str]
    regions: list[str]
    recorder: APIRecorder
    cache_dir: Path | None
    cache_ttl_seconds: int
    dry_run: bool
    verbose: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LiveEdgeEvidence:
    inference_rule: str
    confidence: str
    evidence: str
    api_calls: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "source": "aws_live_inference",
            "inference_rule": self.inference_rule,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "api_calls": list(self.api_calls),
        }


@dataclass(frozen=True)
class PendingLiveEdge:
    source_id: str
    target_ref: str | None
    label: str
    edge_type: EdgeType
    evidence: LiveEdgeEvidence | None = None

    def __iter__(self) -> Iterator[Any]:
        yield self.source_id
        yield self.target_ref
        yield self.label
        yield self.edge_type

    def __getitem__(self, index: int) -> Any:
        return tuple(self)[index]


def _tag_map(tag_items: list[dict[str, Any]] | None, key_name: str = "Key", value_name: str = "Value") -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in tag_items or []:
        key = item.get(key_name)
        value = item.get(value_name)
        if key:
            tags[str(key)] = "" if value is None else str(value)
    return tags


def _resource_name(properties: dict[str, Any], *keys: str, fallback: str) -> str:
    for key in keys:
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return fallback


def _resource_id_from_arn(arn: str) -> str:
    if "/" in arn:
        return arn.rsplit("/", 1)[-1]
    if ":" in arn:
        return arn.rsplit(":", 1)[-1]
    return arn


def _clean_arn_ref(value: str) -> str:
    return value.rstrip("*").rstrip("/")


def _extract_lambda_arn_from_apigw_uri(value: str) -> str | None:
    match = re.search(r"/functions/(arn:aws[a-zA-Z-]*:lambda:[^/]+)/invocations", value)
    if match:
        return match.group(1)
    if value.startswith("arn:") and ":lambda:" in value:
        return _clean_arn_ref(value)
    return None


def _extract_execute_api_id(value: str) -> str | None:
    match = re.match(r"arn:aws[a-zA-Z-]*:execute-api:[^:]+:[^:]+:([^/*:]+)", value)
    return match.group(1) if match else None


def _dns_variants(value: str) -> set[str]:
    cleaned = value.strip().rstrip(".")
    variants = {cleaned}
    if cleaned.startswith("dualstack."):
        variants.add(cleaned.removeprefix("dualstack."))
    if ".cloudfront.net" in cleaned:
        variants.add(cleaned.lower())
    return {variant for variant in variants if variant}


def _edge_metadata(
    inference_rule: str,
    confidence: str,
    evidence: str,
    *api_calls: str,
) -> LiveEdgeEvidence:
    return LiveEdgeEvidence(
        inference_rule=inference_rule,
        confidence=confidence,
        evidence=evidence,
        api_calls=tuple(api_calls),
    )


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _policy_statements(policy_value: Any) -> list[dict[str, Any]]:
    if not policy_value:
        return []
    if isinstance(policy_value, str):
        try:
            policy_value = json.loads(policy_value)
        except Exception:
            return []
    if isinstance(policy_value, dict) and "PolicyDocument" in policy_value:
        policy_value = policy_value.get("PolicyDocument")
    if not isinstance(policy_value, dict):
        return []
    statements = policy_value.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    return [statement for statement in statements if isinstance(statement, dict) and statement.get("Effect", "Allow") == "Allow"]


def _classify_live_actions(actions: list[Any]) -> EdgeType | None:
    has_write = False
    has_read = False
    has_invoke = False
    for raw_action in actions:
        if not isinstance(raw_action, str) or ":" not in raw_action:
            continue
        service, action_name = raw_action.split(":", 1)
        if service in {"logs", "cloudwatch", "xray"}:
            continue
        if action_name == "*" or action_name.endswith("*"):
            if service in {"dynamodb", "s3", "sqs", "sns", "secretsmanager"}:
                has_write = True
                has_read = True
            elif service in {"lambda", "states"}:
                has_invoke = True
            continue
        if action_name in _LIVE_INVOKE_ACTIONS:
            has_invoke = True
        if action_name in _LIVE_WRITE_ACTIONS:
            has_write = True
        if action_name in _LIVE_READ_ACTIONS:
            has_read = True
    if has_invoke:
        return EdgeType.TRIGGERS
    if has_write:
        return EdgeType.WRITES_TO
    if has_read:
        return EdgeType.READS_FROM
    return None


def _action_label_for_edge(edge_type: EdgeType) -> str:
    if edge_type == EdgeType.WRITES_TO:
        return "writes to"
    if edge_type == EdgeType.READS_FROM:
        return "reads from"
    if edge_type == EdgeType.TRIGGERS:
        return "invokes"
    return "references"


def _resolve_policy_resource(
    resource: str,
    nodes: list[StackMapNode],
    resolve_target: Callable[[str | None], str | None],
) -> list[tuple[str, str]]:
    clean = _clean_arn_ref(resource)
    direct = resolve_target(clean)
    if direct:
        return [(direct, "high")]
    if "*" not in resource:
        return []

    prefix = resource.split("*", 1)[0].rstrip("/")
    matches: list[tuple[str, str]] = []
    for node in nodes:
        arn = node.properties.get("arn")
        if isinstance(arn, str) and arn.startswith(prefix):
            matches.append((node.id, "medium"))
    return matches


def _component_group_name(nodes: list[StackMapNode], index: int) -> str:
    for tag_key in ("aws:cloudformation:stack-name", "service", "app", "application", "project", "component"):
        values = [node.tags.get(tag_key) for node in nodes if node.tags.get(tag_key)]
        if values:
            return str(sorted(values, key=len)[0])
    entry = next(
        (
            node for node in nodes
            if node.resource_type in {"aws_api_gateway_rest_api", "aws_apigatewayv2_api", "aws_cloudfront_distribution", "aws_lb"}
        ),
        None,
    )
    if entry:
        return str(entry.name)
    return f"Component {index}"


def _build_live_node(
    *,
    account_id: str,
    region: str,
    resource_type: str,
    resource_id: str,
    name: str,
    properties: dict[str, Any],
    tags: dict[str, str] | None = None,
) -> StackMapNode:
    category = RESOURCE_CATEGORY_MAP.get(resource_type, ResourceCategory.OTHER)
    tier = TIER_MAP.get(category, "backend")
    weight = WEIGHT_MAP.get(resource_type, 2)
    return StackMapNode(
        id=f"aws:{account_id}:{region}:{resource_type}:{resource_id}",
        name=name,
        resource_type=resource_type,
        provider="aws",
        category=category,
        properties=properties,
        tags=tags or {},
        metadata={
            "account_id": account_id,
            "region": region,
            "source_type": "aws_live",
            "source_kind": "live_scan",
        },
        position_hint={
            "tier": tier,
            "weight": weight,
            "account_id": account_id,
            "region": region,
            "source_type": "aws_live",
            "source_kind": "live_scan",
        },
    )


def _group_id(prefix: str, account_id: str, region: str, raw_id: str) -> str:
    return f"group:{prefix}:{account_id}:{region}:{raw_id}"


class AWSAPIExecutor:
    def __init__(self, context: AccountScanContext) -> None:
        self.context = context
        self._clients: dict[tuple[str, str], Any] = {}

    def client(self, service: str, region: str) -> Any:
        key = (service, region)
        if key not in self._clients:
            kwargs: dict[str, Any] = {"region_name": region}
            if service in GLOBAL_SERVICES and self.context.session.region_name:
                kwargs["region_name"] = self.context.session.region_name
            self._clients[key] = self.context.session.client(service, **kwargs)
        return self._clients[key]

    def call(self, service: str, operation: str, *, region: str, **params: Any) -> Any:
        self.context.recorder.plan(self.context.account_id, region, service, operation, params)
        if self.context.dry_run:
            return None

        cache_hit = self._load_cache(service, operation, region, params)
        if cache_hit is not None:
            return cache_hit

        client = self.client(service, region)
        method = getattr(client, operation)
        try:
            response = method(**params)
            self.context.recorder.executed()
            if self.context.verbose:
                self.context.warnings.append(
                    f"API call: {self.context.account_id} {region} {service}.{operation}"
                )
            self._write_cache(service, operation, region, params, response)
            return response
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
                self.context.warnings.append(
                    f"{self.context.account_id}:{region}:{service}.{operation} denied: {code}"
                )
                return None
            raise
        except BotoCoreError as exc:
            self.context.errors.append(
                f"{self.context.account_id}:{region}:{service}.{operation} failed: {exc}"
            )
            return None

    def call_optional(
        self,
        service: str,
        operation: str,
        *,
        region: str,
        swallow_codes: set[str] | None = None,
        **params: Any,
    ) -> Any:
        try:
            return self.call(service, operation, region=region, **params)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            if swallow_codes and code in swallow_codes:
                self.context.warnings.append(
                    f"{self.context.account_id}:{region}:{service}.{operation} skipped: {code}"
                )
                return None
            raise

    def paginate(self, service: str, operation: str, result_key: str, *, region: str, **params: Any) -> list[dict[str, Any]]:
        if self.context.dry_run:
            self.context.recorder.plan(self.context.account_id, region, service, f"paginate:{operation}", params)
            return []

        client = self.client(service, region)
        try:
            paginator = client.get_paginator(operation)
        except Exception:
            response = self.call(service, operation, region=region, **params)
            if not response:
                return []
            values = response.get(result_key, [])
            return values if isinstance(values, list) else []

        collected: list[dict[str, Any]] = []
        try:
            for page in paginator.paginate(**params):
                self.context.recorder.executed()
                values = page.get(result_key, [])
                if isinstance(values, list):
                    collected.extend(values)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
                self.context.warnings.append(
                    f"{self.context.account_id}:{region}:{service}.{operation} denied: {code}"
                )
                return []
            raise
        except BotoCoreError as exc:
            self.context.errors.append(
                f"{self.context.account_id}:{region}:{service}.{operation} failed: {exc}"
            )
            return []
        return collected

    def _cache_key(self, service: str, operation: str, region: str, params: dict[str, Any]) -> Path | None:
        if self.context.cache_dir is None or self.context.dry_run:
            return None
        raw = json.dumps(
            {
                "account_id": self.context.account_id,
                "region": region,
                "service": service,
                "operation": operation,
                "params": params,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        return self.context.cache_dir / self.context.account_id / region / service / f"{operation}-{digest}.json"

    def _load_cache(self, service: str, operation: str, region: str, params: dict[str, Any]) -> Any:
        path = self._cache_key(service, operation, region, params)
        if path is None or not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.context.cache_ttl_seconds:
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _write_cache(self, service: str, operation: str, region: str, params: dict[str, Any], response: Any) -> None:
        path = self._cache_key(service, operation, region, params)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(response, indent=2, default=str))
        except Exception:
            return


class AWSLiveScanner:
    def __init__(
        self,
        *,
        profile: str | None = None,
        regions: list[str] | None = None,
        account_hint: str | None = None,
        role_arn: str | None = None,
        services: set[str] | None = None,
        dry_run: bool = False,
        verbose: bool = False,
        concurrency: int = 4,
        org_file: str | None = None,
        org_scan: bool = False,
        role_name: str = "StackMapReadOnly",
        try_current_creds: bool = False,
        cache_dir: str | None = None,
        no_cache: bool = False,
        partial_write_path: str | None = None,
        sfn_executions: bool = False,
        session_factory: Callable[..., boto3.session.Session] | None = None,
    ) -> None:
        self.profile = profile
        self.regions = regions or []
        self.account_hint = account_hint
        self.role_arn = role_arn
        self.services = services or set(SERVICE_SET_BROAD)
        self.dry_run = dry_run
        self.verbose = verbose
        self.concurrency = max(1, concurrency)
        self.org_file = org_file
        self.org_scan = org_scan
        self.role_name = role_name
        self.try_current_creds = try_current_creds
        self.cache_dir = None if no_cache else Path(cache_dir or "~/.stackmap/cache").expanduser()
        self.partial_write_path = Path(partial_write_path) if partial_write_path else None
        self.sfn_executions = sfn_executions
        self._session_factory = session_factory or boto3.session.Session

    def scan(self) -> StackMapIR:
        if self.org_scan:
            return self._scan_organization()
        base_session, auth_description = self._resolve_base_session()
        session = self._assume_role(base_session, self.role_arn) if self.role_arn else base_session
        account_id = self.account_hint or self._get_account_id(session)
        regions = self._resolve_regions(session)
        context = AccountScanContext(
            session=session,
            account_id=account_id,
            account_name=None,
            auth_description=auth_description if not self.role_arn else f"{auth_description} -> {self.role_arn}",
            role_arn=self.role_arn,
            services=self.services,
            regions=regions,
            recorder=APIRecorder(dry_run=self.dry_run, verbose=self.verbose),
            cache_dir=self.cache_dir,
            cache_ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
            dry_run=self.dry_run,
            verbose=self.verbose,
        )
        ir = self._scan_account(context)
        if self.partial_write_path and not self.dry_run:
            ir.write_json(self.partial_write_path)
        return ir

    def scan_explicit_accounts(
        self, account_roles: list[tuple[str, str]]
    ) -> StackMapIR:
        """Scan multiple explicit accounts by assuming roles via STS.

        Args:
            account_roles: List of (account_id, role_arn) tuples.
        """
        base_session, auth_description = self._resolve_base_session()

        # Resolve regions from the first account if not specified
        if not self.regions:
            first_role_arn = account_roles[0][1] if account_roles else None
            try:
                probe_session = self._assume_role(base_session, first_role_arn)
                regions = self._resolve_regions(probe_session)
            except Exception:
                regions = ["us-east-1"]
        else:
            regions = self.regions

        all_results: list[StackMapIR] = []
        all_errors: list[str] = []

        def scan_one_account(account_id: str, role_arn: str) -> tuple[StackMapIR | None, list[str]]:
            errors: list[str] = []
            try:
                session = self._assume_role(base_session, role_arn)
            except Exception as exc:
                errors.append(f"Failed to assume role for {account_id}: {exc}")
                return None, errors

            context = AccountScanContext(
                session=session,
                account_id=account_id,
                account_name=None,
                auth_description=f"{auth_description} -> {role_arn}",
                role_arn=role_arn,
                services=self.services,
                regions=regions,
                recorder=APIRecorder(dry_run=self.dry_run, verbose=self.verbose),
                cache_dir=self.cache_dir,
                cache_ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
                dry_run=self.dry_run,
                verbose=self.verbose,
            )
            try:
                ir = self._scan_account(context)
                errors.extend(context.errors)
                return ir, errors
            except Exception as exc:
                errors.append(f"Scan failed for {account_id}: {exc}")
                return None, errors

        if self.verbose:
            from rich.console import Console as RichConsole
            verbose_console = RichConsole(stderr=True)

        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(account_roles))) as pool:
            futures = {
                pool.submit(scan_one_account, acct_id, role): (acct_id, role)
                for acct_id, role in account_roles
            }
            for future in as_completed(futures):
                acct_id, role = futures[future]
                ir, errors = future.result()
                all_errors.extend(errors)
                if ir is not None:
                    all_results.append(ir)
                    if self.verbose:
                        verbose_console.print(
                            f"[green]✓[/green] {acct_id}: {len(ir.nodes)} resources"
                        )

        # Merge all results
        merged = StackMapIR(
            metadata={
                "source_type": "aws_live",
                "source_kind": "live_scan",
                "scan_mode": "multi_account",
                "accounts": [acct_id for acct_id, _ in account_roles],
                "regions": regions,
                "selected_services": sorted(self.services),
                "auth_mode": f"explicit multi-account via {auth_description}",
            },
            nodes=[],
            edges=[],
            groups=[],
        )

        for ir in all_results:
            merged.nodes.extend(ir.nodes)
            merged.edges.extend(ir.edges)
            merged.groups.extend(ir.groups)

        if all_errors:
            merged.metadata["errors"] = all_errors

        # Create account groups
        for account_id, _ in account_roles:
            account_nodes = [n for n in merged.nodes if n.metadata.get("account_id") == account_id]
            if account_nodes:
                merged.groups.append(
                    StackMapGroup(
                        id=f"group:account:{account_id}",
                        name=account_id,
                        group_type="account",
                        children=[n.id for n in account_nodes],
                        parent=None,
                        metadata={"account_id": account_id},
                    )
                )

        # Infer cross-account edges
        infer_cross_account_edges(merged)

        return merged

    def scan_explicit_profiles(
        self, profiles: list[str]
    ) -> StackMapIR:
        """Scan multiple explicit AWS profiles.

        Args:
            profiles: List of AWS shared-config profile names.
        """
        profile_sessions: list[tuple[str, boto3.session.Session, str]] = []
        all_errors: list[str] = []

        for profile in profiles:
            try:
                session = self._session_factory(profile_name=profile)
                creds = session.get_credentials()
                if creds is None:
                    all_errors.append(f"Profile '{profile}' has no credentials")
                    continue
                account_id = self._get_account_id(session)
                profile_sessions.append((profile, session, account_id))
            except Exception as exc:
                all_errors.append(f"Failed to initialize profile '{profile}': {exc}")

        if not profile_sessions:
            raise RuntimeError("No valid AWS profiles could be initialized for multi-account scan.")

        if not self.regions:
            try:
                regions = self._resolve_regions(profile_sessions[0][1])
            except Exception:
                regions = ["us-east-1"]
        else:
            regions = self.regions

        all_results: list[StackMapIR] = []

        def scan_one_profile(
            profile_name: str,
            session: boto3.session.Session,
            account_id: str,
        ) -> tuple[StackMapIR | None, list[str]]:
            errors: list[str] = []
            context = AccountScanContext(
                session=session,
                account_id=account_id,
                account_name=profile_name,
                auth_description=f"profile '{profile_name}'",
                role_arn=None,
                services=self.services,
                regions=regions,
                recorder=APIRecorder(dry_run=self.dry_run, verbose=self.verbose),
                cache_dir=self.cache_dir,
                cache_ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
                dry_run=self.dry_run,
                verbose=self.verbose,
            )
            try:
                ir = self._scan_account(context)
                ir.metadata["profile"] = profile_name
                errors.extend(context.errors)
                return ir, errors
            except Exception as exc:
                errors.append(f"Scan failed for profile '{profile_name}' ({account_id}): {exc}")
                return None, errors

        if self.verbose:
            from rich.console import Console as RichConsole
            verbose_console = RichConsole(stderr=True)

        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(profile_sessions))) as pool:
            futures = {
                pool.submit(scan_one_profile, profile, session, account_id): (profile, account_id)
                for profile, session, account_id in profile_sessions
            }
            for future in as_completed(futures):
                profile_name, account_id = futures[future]
                ir, errors = future.result()
                all_errors.extend(errors)
                if ir is not None:
                    all_results.append(ir)
                    if self.verbose:
                        verbose_console.print(
                            f"[green]✓[/green] {profile_name} ({account_id}): {len(ir.nodes)} resources"
                        )

        merged = StackMapIR(
            metadata={
                "source_type": "aws_live",
                "source_kind": "live_scan",
                "scan_mode": "multi_account",
                "accounts": [account_id for _, _, account_id in profile_sessions],
                "profiles": profiles,
                "regions": regions,
                "selected_services": sorted(self.services),
                "auth_mode": "explicit multi-account via AWS profiles",
            },
            nodes=[],
            edges=[],
            groups=[],
        )

        for ir in all_results:
            merged.nodes.extend(ir.nodes)
            merged.edges.extend(ir.edges)
            merged.groups.extend(ir.groups)

        if all_errors:
            merged.metadata["errors"] = all_errors

        for profile_name, _, account_id in profile_sessions:
            account_nodes = [n for n in merged.nodes if n.metadata.get("account_id") == account_id]
            if account_nodes:
                merged.groups.append(
                    StackMapGroup(
                        id=f"group:account:{account_id}",
                        name=profile_name,
                        group_type="account",
                        children=[n.id for n in account_nodes],
                        parent=None,
                        metadata={"account_id": account_id, "account_name": profile_name},
                    )
                )

        infer_cross_account_edges(merged)
        return merged

    def startup_summary(self) -> dict[str, Any]:
        session, auth_description = self._resolve_base_session()
        resolved_session = self._assume_role(session, self.role_arn) if self.role_arn else session
        account_id = self.account_hint or self._get_account_id(resolved_session)
        regions = self._resolve_regions(resolved_session)
        return {
            "account_id": account_id,
            "regions": regions,
            "auth_description": auth_description if not self.role_arn else f"{auth_description} -> {self.role_arn}",
            "org_scan": self.org_scan,
            "services": sorted(self.services),
        }

    def dry_run_plan(self) -> list[PlannedAPICall]:
        session, auth_description = self._resolve_base_session()
        if self.org_scan:
            org = self._load_or_discover_org(session)
            plans: list[PlannedAPICall] = []
            for account in org.accounts:
                role_arn = f"arn:aws:iam::{account['id']}:role/{self.role_name}"
                assumed = self._assume_role(session, role_arn)
                context = AccountScanContext(
                    session=assumed,
                    account_id=account["id"],
                    account_name=account.get("name"),
                    auth_description=auth_description,
                    role_arn=role_arn,
                    services=self.services,
                    regions=self._resolve_regions(assumed),
                    recorder=APIRecorder(dry_run=True, verbose=self.verbose),
                    cache_dir=None,
                    cache_ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
                    dry_run=True,
                    verbose=self.verbose,
                )
                self._plan_account(context)
                plans.extend(context.recorder.planned)
            return plans

        resolved = self._assume_role(session, self.role_arn) if self.role_arn else session
        context = AccountScanContext(
            session=resolved,
            account_id=self.account_hint or self._get_account_id(resolved),
            account_name=None,
            auth_description=auth_description,
            role_arn=self.role_arn,
            services=self.services,
            regions=self._resolve_regions(resolved),
            recorder=APIRecorder(dry_run=True, verbose=self.verbose),
            cache_dir=None,
            cache_ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
            dry_run=True,
            verbose=self.verbose,
        )
        self._plan_account(context)
        return context.recorder.planned

    def _scan_organization(self) -> StackMapIR:
        base_session, auth_description = self._resolve_base_session()
        org = self._load_or_discover_org(base_session)
        merged = StackMapIR(
            metadata={
                "source_type": "aws_live",
                "scan_mode": "organization",
                "selected_services": sorted(self.services),
                "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "accounts": [],
                "warnings": [],
                "errors": [],
            }
        )

        def scan_account(account: dict[str, Any]) -> tuple[dict[str, Any], StackMapIR | None]:
            role_arn = f"arn:aws:iam::{account['id']}:role/{self.role_name}"
            session = None
            used_auth = auth_description
            # Try assume-role first, fall back to current creds if enabled
            try:
                session = self._assume_role(base_session, role_arn)
                used_auth = f"{auth_description} -> {role_arn}"
            except Exception as assume_exc:
                if self.try_current_creds:
                    # Fall back to current credentials for this account
                    try:
                        caller_account = self._get_account_id(base_session)
                    except Exception:
                        caller_account = None
                    if caller_account == account["id"]:
                        session = base_session
                        used_auth = f"{auth_description} (direct, assume-role unavailable)"
                        merged.metadata.setdefault("warnings", []).append(
                            f"{account['id']}: assume-role failed ({assume_exc}), using current credentials"
                        )
                    else:
                        merged.metadata["errors"].append(
                            f"{account['id']}: assume-role failed and current creds belong to {caller_account}, not {account['id']}"
                        )
                        return account, None
                else:
                    merged.metadata["errors"].append(f"{account['id']}: {assume_exc}")
                    return account, None
            try:
                context = AccountScanContext(
                    session=session,
                    account_id=account["id"],
                    account_name=account.get("name"),
                    auth_description=used_auth,
                    role_arn=role_arn if session is not base_session else None,
                    services=self.services,
                    regions=self._resolve_regions(session),
                    recorder=APIRecorder(dry_run=self.dry_run, verbose=self.verbose),
                    cache_dir=self.cache_dir,
                    cache_ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
                    dry_run=self.dry_run,
                    verbose=self.verbose,
                )
                result_ir = self._scan_account(context)
                result_ir.metadata["account_name"] = account.get("name")
                result_ir.metadata["account_id"] = account["id"]
                result_ir.metadata["warnings"] = context.warnings
                result_ir.metadata["errors"] = context.errors
                return account, result_ir
            except Exception as exc:
                merged.metadata["errors"].append(f"{account['id']}: {exc}")
                return account, None

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {executor.submit(scan_account, account): account for account in org.accounts}
            for future in as_completed(futures):
                account, account_ir = future.result()
                merged.metadata["accounts"].append(
                    {
                        "id": account["id"],
                        "name": account.get("name"),
                        "scanned": account_ir is not None,
                    }
                )
                if account_ir is None:
                    continue
                merged.nodes.extend(account_ir.nodes)
                merged.edges.extend(account_ir.edges)
                merged.groups.extend(account_ir.groups)
                merged.metadata["warnings"].extend(account_ir.metadata.get("warnings", []))
                merged.metadata["errors"].extend(account_ir.metadata.get("errors", []))
                if self.partial_write_path and not self.dry_run:
                    partial = StackMapIR(
                        metadata={**merged.metadata},
                        nodes=list(merged.nodes),
                        edges=list(merged.edges),
                        groups=list(merged.groups),
                    )
                    overlay_organization_groups(partial, org=org, strict=False)
                    infer_cross_account_edges(partial)
                    partial.write_json(self.partial_write_path)

        overlay_organization_groups(merged, org=org, strict=False)
        merged.metadata["organization"] = org.to_dict()
        merged.metadata["auth_mode"] = auth_description
        merged.metadata["source_kind"] = "live_scan"
        merged.metadata["api_calls"] = sum(
            0 if self.dry_run else 1 for _ in merged.metadata.get("accounts", [])
        )
        infer_cross_account_edges(merged)
        return merged

    def _load_or_discover_org(self, session: boto3.session.Session) -> OrganizationDocument:
        if self.org_file:
            return load_organization_document(self.org_file)
        try:
            return build_org_document_from_session(session)
        except Exception as exc:
            raise RuntimeError(
                "Unable to discover AWS Organizations automatically. "
                "Ensure this principal can call Organizations APIs, or provide --org-file."
            ) from exc

    def _resolve_base_session(self) -> tuple[boto3.session.Session, str]:
        session = self._session_factory(profile_name=self.profile) if self.profile else self._session_factory()
        creds = session.get_credentials()
        if creds is None:
            raise RuntimeError("No AWS credentials found. Configure a profile or environment credentials first.")
        auth_method = getattr(creds, "method", "unknown")
        if self.profile:
            return session, f"profile '{self.profile}' via {auth_method}"
        env_profile = os.environ.get("AWS_PROFILE")
        if env_profile:
            return session, f"profile '{env_profile}' via {auth_method}"
        return session, auth_method

    def _assume_role(self, session: boto3.session.Session, role_arn: str | None) -> boto3.session.Session:
        if not role_arn:
            return session
        sts = session.client("sts")
        resp = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="stackmap-live-scan",
            DurationSeconds=3600,
        )
        creds = resp["Credentials"]
        return self._session_factory(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )

    def _get_account_id(self, session: boto3.session.Session) -> str:
        return session.client("sts").get_caller_identity()["Account"]

    def _resolve_regions(self, session: boto3.session.Session) -> list[str]:
        if self.regions:
            return self.regions
        if self.dry_run:
            return ["us-east-1"]
        try:
            client = session.client("ec2", region_name=session.region_name or "us-east-1")
            response = client.describe_regions(AllRegions=False)
            return sorted(region["RegionName"] for region in response.get("Regions", []))
        except Exception:
            return sorted(session.get_available_regions("ec2"))[:6]

    def _plan_account(self, context: AccountScanContext) -> None:
        executor = AWSAPIExecutor(context)
        for region, service in self._service_scan_targets(context):
            self._collect_service(service, region, executor, plan_only=True)

    def _service_scan_targets(self, context: AccountScanContext) -> list[tuple[str, str]]:
        primary_region = context.regions[0] if context.regions else "us-east-1"
        targets: list[tuple[str, str]] = []
        for service in sorted(context.services):
            if service in GLOBAL_SERVICES:
                targets.append((primary_region, service))
                continue
            for region in context.regions:
                targets.append((region, service))
        return targets

    def _scan_account(self, context: AccountScanContext) -> StackMapIR:
        nodes: list[StackMapNode] = []
        pending_edges: list[tuple[str, str | None, str, EdgeType]] = []
        groups: list[StackMapGroup] = []

        def scan_region(region: str) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup], list[str], list[str]]:
            regional_nodes: list[StackMapNode] = []
            regional_pending_edges: list[tuple[str, str | None, str, EdgeType]] = []
            regional_groups: list[StackMapGroup] = []
            regional_warnings: list[str] = []
            regional_errors: list[str] = []
            executor = AWSAPIExecutor(context)
            for service in sorted(context.services):
                if service in GLOBAL_SERVICES and region != (context.regions[0] if context.regions else region):
                    continue
                try:
                    service_nodes, service_pending, service_groups = self._collect_service(service, region, executor)
                    regional_nodes.extend(service_nodes)
                    regional_pending_edges.extend(service_pending)
                    regional_groups.extend(service_groups)
                except Exception as exc:
                    regional_errors.append(f"{context.account_id}:{region}:{service}: {exc}")
            return regional_nodes, regional_pending_edges, regional_groups, regional_warnings, regional_errors

        unique_regions = sorted({region for region, _service in self._service_scan_targets(context)})
        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(unique_regions))) as pool:
            futures = {pool.submit(scan_region, region): region for region in unique_regions}
            for future in as_completed(futures):
                regional_nodes, regional_pending_edges, regional_groups, _warnings, regional_errors = future.result()
                nodes.extend(regional_nodes)
                pending_edges.extend(regional_pending_edges)
                groups.extend(regional_groups)
                context.errors.extend(regional_errors)
                if self.partial_write_path and not self.dry_run:
                    partial_ir = self._build_ir(context, list(nodes), list(pending_edges), list(groups))
                    partial_ir.write_json(self.partial_write_path)

        ir = self._build_ir(context, nodes, pending_edges, groups)
        return ir

    def _build_ir(
        self,
        context: AccountScanContext,
        nodes: list[StackMapNode],
        pending_edges: list[tuple[str, str | None, str, EdgeType] | PendingLiveEdge],
        groups: list[StackMapGroup],
    ) -> StackMapIR:
        node_by_id = {node.id: node for node in nodes}
        arn_index: dict[str, str] = {}
        id_index: dict[str, str] = {}
        bucket_name_index: dict[str, str] = {}
        dns_index: dict[str, str] = {}

        for node in nodes:
            id_index[node.id] = node.id
            if isinstance(node.properties.get("arn"), str):
                arn = str(node.properties["arn"])
                arn_index[arn] = node.id
                arn_index[_clean_arn_ref(arn)] = node.id
            for key in (
                "id",
                "name",
                "function_name",
                "bucket",
                "url",
                "domain_name",
                "dns_name",
                "role_name",
                "queue_name",
                "topic_name",
            ):
                value = node.properties.get(key)
                if isinstance(value, str) and value:
                    id_index[value] = node.id
                    id_index[_clean_arn_ref(value)] = node.id
            if node.resource_type == "aws_s3_bucket" and isinstance(node.properties.get("bucket"), str):
                bucket_name = str(node.properties["bucket"])
                bucket_name_index[bucket_name] = node.id
                bucket_name_index[f"{bucket_name}.s3.amazonaws.com"] = node.id
                region = str(node.metadata.get("region") or "")
                if region:
                    bucket_name_index[f"{bucket_name}.s3.{region}.amazonaws.com"] = node.id
                regional_domain = node.properties.get("bucket_regional_domain_name")
                if isinstance(regional_domain, str) and regional_domain:
                    bucket_name_index[regional_domain] = node.id
            if isinstance(node.properties.get("dns_name"), str):
                for variant in _dns_variants(str(node.properties["dns_name"])):
                    dns_index[variant] = node.id
            if isinstance(node.properties.get("domain_name"), str):
                for variant in _dns_variants(str(node.properties["domain_name"])):
                    dns_index[variant] = node.id
            for domain_key in ("bucket_domain_name", "bucket_regional_domain_name"):
                if isinstance(node.properties.get(domain_key), str):
                    for variant in _dns_variants(str(node.properties[domain_key])):
                        bucket_name_index[variant] = node.id

        edges: list[StackMapEdge] = []
        seen: set[tuple[str, str, str]] = set()

        def add_edge(
            source_id: str,
            target_id: str,
            label: str,
            edge_type: EdgeType,
            evidence: LiveEdgeEvidence | None = None,
        ) -> None:
            if source_id not in node_by_id:
                return
            if target_id not in node_by_id or target_id == source_id:
                return
            key = (source_id, target_id, edge_type.value)
            if key in seen:
                return
            seen.add(key)
            edges.append(
                StackMapEdge(
                    id=f"{source_id}->{target_id}:{edge_type.value}",
                    source=source_id,
                    target=target_id,
                    edge_type=edge_type,
                    label=label,
                    metadata=evidence.to_metadata() if evidence else {},
                )
            )

        def resolve_target(target_ref: str | None) -> str | None:
            if not target_ref:
                return None
            candidates = [target_ref, _clean_arn_ref(target_ref)]
            candidates.extend(sorted(_dns_variants(target_ref)))
            lambda_arn = _extract_lambda_arn_from_apigw_uri(target_ref)
            if lambda_arn:
                candidates.extend([lambda_arn, _clean_arn_ref(lambda_arn)])
            for candidate in candidates:
                target_id = (
                    arn_index.get(candidate)
                    or id_index.get(candidate)
                    or bucket_name_index.get(candidate)
                    or dns_index.get(candidate)
                )
                if target_id:
                    return target_id
            return None

        for pending in pending_edges:
            if isinstance(pending, PendingLiveEdge):
                source_id = pending.source_id
                target_ref = pending.target_ref
                label = pending.label
                edge_type = pending.edge_type
                evidence = pending.evidence
            else:
                source_id, target_ref, label, edge_type = pending
                evidence = None
            target_id = resolve_target(target_ref)
            if target_id:
                if evidence is None:
                    evidence = _edge_metadata(
                        "direct_reference",
                        "high" if edge_type != EdgeType.REFERENCES else "medium",
                        f"{label} references {target_ref}",
                    )
                add_edge(source_id, target_id, label, edge_type, evidence)

        self._infer_live_relationships(nodes, add_edge, resolve_target)

        inference_counts: dict[str, int] = {}
        confidence_counts: dict[str, int] = {}
        for edge in edges:
            rule = edge.metadata.get("inference_rule")
            confidence = edge.metadata.get("confidence")
            if rule:
                inference_counts[str(rule)] = inference_counts.get(str(rule), 0) + 1
            if confidence:
                confidence_counts[str(confidence)] = confidence_counts.get(str(confidence), 0) + 1

        group_map = {group.id: group for group in groups}
        child_sets: dict[str, set[str]] = {group.id: set(group.children) for group in groups}
        for node in nodes:
            account_id = str(node.metadata.get("account_id") or context.account_id)
            region = str(node.metadata.get("region") or "global")
            vpc_id = node.properties.get("vpc_id")
            if isinstance(vpc_id, str) and vpc_id:
                vpc_group_id = _group_id("vpc", account_id, region, vpc_id)
                if vpc_group_id in group_map:
                    child_sets.setdefault(vpc_group_id, set()).add(node.id)
            subnet_id = node.properties.get("subnet_id")
            if isinstance(subnet_id, str) and subnet_id:
                subnet_group_id = _group_id("subnet", account_id, region, subnet_id)
                if subnet_group_id in group_map:
                    child_sets.setdefault(subnet_group_id, set()).add(node.id)
            subnet_ids = node.properties.get("subnet_ids")
            if isinstance(subnet_ids, list):
                for subnet in subnet_ids:
                    if not isinstance(subnet, str) or not subnet:
                        continue
                    subnet_group_id = _group_id("subnet", account_id, region, subnet)
                    if subnet_group_id in group_map:
                        child_sets.setdefault(subnet_group_id, set()).add(node.id)

        # Resource types that are VPC infrastructure rather than workloads
        _VPC_INFRA_TYPES = {"aws_vpc", "aws_subnet", "aws_security_group"}

        normalized_groups: list[StackMapGroup] = []
        for group in groups:
            group.children = sorted(child_sets.get(group.id, set()))
            if group.group_type in {"vpc", "subnet"} and not group.children:
                continue
            # Suppress VPC groups that only contain infrastructure (subnets/SGs) but no workloads
            if group.group_type == "vpc" and group.children:
                has_workload = any(
                    node_by_id[child].resource_type not in _VPC_INFRA_TYPES
                    for child in group.children
                    if child in node_by_id
                )
                if not has_workload:
                    continue
            normalized_groups.append(group)

        ir = StackMapIR(
            metadata={
                "source_type": "aws_live",
                "source_kind": "live_scan",
                "scan_mode": "single_account",
                "account_id": context.account_id,
                "account_name": context.account_name,
                "regions": context.regions,
                "selected_services": sorted(context.services),
                "auth_mode": context.auth_description,
                "warnings": context.warnings,
                "errors": context.errors,
                "dry_run": context.dry_run,
                "api_calls": context.recorder.actual_count,
                "live_inference": {
                    "edge_count": len(edges),
                    "rules": inference_counts,
                    "confidence": confidence_counts,
                },
                "planned_api_calls": [
                    {
                        "account_id": call.account_id,
                        "region": call.region,
                        "service": call.service,
                        "operation": call.operation,
                        "params": call.params,
                    }
                    for call in context.recorder.planned
                ],
            },
            nodes=nodes,
            edges=edges,
            groups=normalized_groups,
        )
        self._apply_live_smart_groups(ir)
        overlay_organization_groups(ir, org=load_organization_document(self.org_file) if self.org_file else None, strict=False)
        ir.metadata["cross_account_edges"] = infer_cross_account_edges(ir)
        return ir

    def _infer_live_relationships(
        self,
        nodes: list[StackMapNode],
        add_edge: Callable[[str, str, str, EdgeType, LiveEdgeEvidence | None], None],
        resolve_target: Callable[[str | None], str | None],
    ) -> None:
        """Infer cross-service live relationships from collected AWS facts."""
        nodes_by_id = {node.id: node for node in nodes}
        nodes_by_arn = {
            str(node.properties.get("arn")): node
            for node in nodes
            if isinstance(node.properties.get("arn"), str)
        }
        api_by_execute_id = {
            str(node.properties.get("id")): node
            for node in nodes
            if node.resource_type in {"aws_api_gateway_rest_api", "aws_apigatewayv2_api"}
            and isinstance(node.properties.get("id"), str)
        }
        task_definition_consumers: dict[str, list[StackMapNode]] = {}
        for node in nodes:
            if node.resource_type != "aws_ecs_service":
                continue
            task_definition = node.properties.get("task_definition")
            if isinstance(task_definition, str) and task_definition:
                task_definition_consumers.setdefault(task_definition, []).append(node)

        role_to_principals: dict[str, list[StackMapNode]] = {}
        for node in nodes:
            role_arn = node.properties.get("role_arn") or node.properties.get("task_role_arn")
            if isinstance(role_arn, str) and role_arn:
                principals = role_to_principals.setdefault(role_arn, [])
                principals.append(node)
                if node.resource_type == "aws_ecs_task_definition":
                    node_arn = node.properties.get("arn")
                    if isinstance(node_arn, str):
                        principals.extend(task_definition_consumers.get(node_arn, []))

        for api in api_by_execute_id.values():
            for uri in api.properties.get("integration_uris", []) or []:
                if not isinstance(uri, str):
                    continue
                lambda_arn = _extract_lambda_arn_from_apigw_uri(uri)
                target_id = resolve_target(lambda_arn or uri)
                if target_id:
                    add_edge(
                        api.id,
                        target_id,
                        "invokes",
                        EdgeType.TRIGGERS,
                        _edge_metadata(
                            "apigateway_lambda_integration_uri",
                            "high",
                            f"API Gateway integration URI references {lambda_arn or uri}",
                            "apigateway:get_integration",
                            "apigatewayv2:get_integrations",
                        ),
                    )

        for fn in nodes:
            if fn.resource_type != "aws_lambda_function":
                continue
            for statement in _policy_statements(fn.properties.get("resource_policy")):
                principal = statement.get("Principal")
                principal_text = json.dumps(principal, default=str)
                if "apigateway.amazonaws.com" not in principal_text:
                    continue
                source_arn = statement.get("Condition", {}).get("ArnLike", {}).get("AWS:SourceArn")
                if not isinstance(source_arn, str):
                    source_arn = statement.get("Condition", {}).get("ArnEquals", {}).get("AWS:SourceArn")
                api_id = _extract_execute_api_id(source_arn) if isinstance(source_arn, str) else None
                api = api_by_execute_id.get(api_id or "")
                if api:
                    add_edge(
                        api.id,
                        fn.id,
                        "invokes",
                        EdgeType.TRIGGERS,
                        _edge_metadata(
                            "lambda_policy_execute_api_source_arn",
                            "medium",
                            f"Lambda policy allows API Gateway SourceArn {source_arn}",
                            "lambda:get_policy",
                        ),
                    )

        for role_arn, principals in role_to_principals.items():
            role = nodes_by_arn.get(role_arn)
            if not role:
                continue
            for policy in role.properties.get("policies", []) or []:
                for statement in _policy_statements(policy):
                    edge_type = _classify_live_actions(_as_list(statement.get("Action")))
                    if edge_type is None:
                        continue
                    for resource in _as_list(statement.get("Resource")):
                        if not isinstance(resource, str) or resource == "*":
                            continue
                        for target_id, confidence in _resolve_policy_resource(resource, nodes, resolve_target):
                            target_node = nodes_by_id.get(target_id)
                            if target_node and target_node.resource_type == "aws_cloudwatch_log_group":
                                continue
                            for principal in principals:
                                add_edge(
                                    principal.id,
                                    target_id,
                                    _action_label_for_edge(edge_type),
                                    edge_type,
                                    _edge_metadata(
                                        "iam_role_policy_resource_access",
                                        confidence,
                                        f"{principal.name} role policy grants {statement.get('Action')} on {resource}",
                                        "iam:get_role_policy",
                                        "iam:get_policy_version",
                                    ),
                                )

        for service in nodes:
            if service.resource_type != "aws_ecs_service":
                continue
            for tg_arn in service.properties.get("target_group_arns", []) or []:
                if not isinstance(tg_arn, str):
                    continue
                target_group_id = resolve_target(tg_arn)
                if target_group_id:
                    add_edge(
                        target_group_id,
                        service.id,
                        "routes to",
                        EdgeType.ROUTES_TO,
                        _edge_metadata(
                            "ecs_service_target_group",
                            "high",
                            f"ECS service is registered with target group {tg_arn}",
                            "ecs:describe_services",
                        ),
                    )

    def _apply_live_smart_groups(self, ir: StackMapIR) -> None:
        """Create app/component groups for live scans using tags and inferred edges."""
        if ir.metadata.get("source_type") != "aws_live":
            return

        # VPC/subnet groups are topology context; they should not prevent
        # business/component groups from claiming the same workloads.
        existing_children = {
            child
            for group in ir.groups
            if group.group_type not in {"vpc", "subnet"}
            for child in group.children
        }
        groups: list[StackMapGroup] = []

        def add_group(group_id: str, name: str, children: list[str], metadata: dict[str, Any]) -> None:
            unique_children = sorted({child for child in children if child not in existing_children})
            if len(unique_children) < 2:
                return
            existing_children.update(unique_children)
            node_lookup = {node.id: node for node in ir.nodes}
            accounts = sorted({
                str(node_lookup[child].metadata.get("account_id"))
                for child in unique_children
                if child in node_lookup and node_lookup[child].metadata.get("account_id")
            })
            regions = sorted({
                str(node_lookup[child].metadata.get("region"))
                for child in unique_children
                if child in node_lookup and node_lookup[child].metadata.get("region")
            })
            type_counts: dict[str, int] = {}
            for child in unique_children:
                node = node_lookup.get(child)
                if node:
                    type_counts[node.resource_type] = type_counts.get(node.resource_type, 0) + 1
            groups.append(StackMapGroup(
                id=group_id,
                name=name,
                group_type="smart_group",
                children=unique_children,
                metadata={
                    **metadata,
                    "accounts": accounts,
                    "regions": regions,
                    "resource_count_by_type": type_counts,
                },
            ))

        for tag_key in ("aws:cloudformation:stack-name", "service", "app", "application", "project", "component"):
            clusters: dict[str, list[str]] = {}
            for node in ir.nodes:
                tag_value = node.tags.get(tag_key)
                if tag_value:
                    clusters.setdefault(tag_value, []).append(node.id)
            for tag_value, node_ids in clusters.items():
                add_group(
                    f"live:{tag_key}:{tag_value}".replace(" ", "_").lower(),
                    tag_value,
                    node_ids,
                    {
                        "auto_strategy": "cloudformation_stack" if tag_key.startswith("aws:cloudformation") else "business_tag",
                        "confidence": "high",
                        "evidence": f"Grouped by tag {tag_key}={tag_value}",
                    },
                )

        adj: dict[str, set[str]] = {}
        for edge in ir.edges:
            confidence = edge.metadata.get("confidence", "medium")
            if edge.edge_type not in _FUNCTIONAL_EDGE_TYPES or confidence == "low":
                continue
            adj.setdefault(edge.source, set()).add(edge.target)
            adj.setdefault(edge.target, set()).add(edge.source)

        visited: set[str] = set()
        component_index = 1
        for node in ir.nodes:
            if node.id in visited or node.id in existing_children:
                continue
            queue = [node.id]
            component: list[str] = []
            while queue:
                current = queue.pop(0)
                if current in visited or current in existing_children:
                    continue
                visited.add(current)
                component.append(current)
                queue.extend(sorted(adj.get(current, set()) - visited))
            if len(component) < 3:
                continue
            component_nodes = [n for n in ir.nodes if n.id in component]
            entrypoints = [
                n.id for n in component_nodes
                if n.resource_type in {"aws_api_gateway_rest_api", "aws_apigatewayv2_api", "aws_cloudfront_distribution", "aws_lb"}
            ]
            name = _component_group_name(component_nodes, component_index)
            add_group(
                f"live:component:{component_index}",
                name,
                component,
                {
                    "auto_strategy": "inferred_service_graph",
                    "confidence": "medium",
                    "evidence": "Grouped by high/medium-confidence live relationships",
                    "entrypoints": entrypoints,
                },
            )
            component_index += 1

        ir.groups.extend(groups)

    def _collect_service(
        self,
        service: str,
        region: str,
        executor: AWSAPIExecutor,
        plan_only: bool = False,
    ) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        if plan_only:
            planner = getattr(self, f"_plan_{service}", None)
            if planner:
                planner(region, executor)
            return [], [], []
        collector = getattr(self, f"_collect_{service}", None)
        if collector is None:
            return [], [], []
        return collector(region, executor)

    def _plan_ec2(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("ec2", "describe_vpcs", region=region)
        executor.call("ec2", "describe_subnets", region=region)
        executor.call("ec2", "describe_security_groups", region=region)
        executor.call("ec2", "describe_instances", region=region)

    def _plan_elbv2(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("elbv2", "describe_load_balancers", region=region)
        executor.call("elbv2", "describe_target_groups", region=region)

    def _plan_lambda(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("lambda", "list_functions", region=region)
        executor.call("lambda", "list_event_source_mappings", region=region)

    def _plan_apigateway(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("apigateway", "get_rest_apis", region=region)
        executor.call("apigatewayv2", "get_apis", region=region)

    def _plan_ecs(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("ecs", "list_clusters", region=region)

    def _plan_rds(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("rds", "describe_db_instances", region=region)
        executor.call("rds", "describe_db_clusters", region=region)

    def _plan_dynamodb(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("dynamodb", "list_tables", region=region)

    def _plan_s3(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("s3", "list_buckets", region=region)

    def _plan_cloudfront(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("cloudfront", "list_distributions", region=region)

    def _plan_route53(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("route53", "list_hosted_zones", region=region)

    def _plan_sqs(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("sqs", "list_queues", region=region)

    def _plan_sns(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("sns", "list_topics", region=region)

    def _plan_iam(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("iam", "list_roles", region=region)

    def _plan_elasticache(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("elasticache", "describe_cache_clusters", region=region)
        executor.call("elasticache", "describe_replication_groups", region=region)

    def _plan_secretsmanager(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("secretsmanager", "list_secrets", region=region)

    def _plan_eventbridge(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("events", "list_rules", region=region)

    def _plan_cognito(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("cognito-idp", "list_user_pools", region=region, MaxResults=60)
        executor.call("cognito-identity", "list_identity_pools", region=region, MaxResults=60)

    def _plan_stepfunctions(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("stepfunctions", "list_state_machines", region=region)

    def _plan_ecr(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("ecr", "describe_repositories", region=region)

    def _plan_appsync(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("appsync", "list_graphql_apis", region=region)

    def _plan_tagging(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("resourcegroupstaggingapi", "get_resources", region=region)

    def _plan_config(self, region: str, executor: AWSAPIExecutor) -> None:
        executor.call("config", "list_discovered_resources", region=region, resourceType="AWS::EC2::VPC")

    def _collect_ec2(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        groups: list[StackMapGroup] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []

        vpcs_resp = executor.call("ec2", "describe_vpcs", region=region) or {}
        subnets_resp = executor.call("ec2", "describe_subnets", region=region) or {}
        sgs_resp = executor.call("ec2", "describe_security_groups", region=region) or {}
        instances_resp = executor.call("ec2", "describe_instances", region=region) or {}

        vpc_nodes: dict[str, str] = {}
        for vpc in vpcs_resp.get("Vpcs", []):
            vpc_id = vpc["VpcId"]
            tags = _tag_map(vpc.get("Tags"))
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_vpc",
                resource_id=vpc_id,
                name=tags.get("Name", vpc_id),
                properties={
                    "id": vpc_id,
                    "arn": vpc.get("VpcArn") or f"arn:aws:ec2:{region}:{account_id}:vpc/{vpc_id}",
                    "cidr_block": vpc.get("CidrBlock"),
                    "state": vpc.get("State"),
                },
                tags=tags,
            )
            nodes.append(node)
            vpc_nodes[vpc_id] = node.id
            groups.append(
                StackMapGroup(
                    id=_group_id("vpc", account_id, region, vpc_id),
                    name=node.name,
                    group_type="vpc",
                    children=[],
                )
            )

        for subnet in subnets_resp.get("Subnets", []):
            subnet_id = subnet["SubnetId"]
            tags = _tag_map(subnet.get("Tags"))
            vpc_id = subnet.get("VpcId", "")
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_subnet",
                resource_id=subnet_id,
                name=tags.get("Name", subnet_id),
                properties={
                    "id": subnet_id,
                    "arn": subnet.get("SubnetArn") or f"arn:aws:ec2:{region}:{account_id}:subnet/{subnet_id}",
                    "vpc_id": vpc_id,
                    "cidr_block": subnet.get("CidrBlock"),
                    "availability_zone": subnet.get("AvailabilityZone"),
                },
                tags=tags,
            )
            nodes.append(node)
            if vpc_id in vpc_nodes:
                pending.append((node.id, vpc_nodes[vpc_id], "in vpc", EdgeType.REFERENCES))
            groups.append(
                StackMapGroup(
                    id=_group_id("subnet", account_id, region, subnet_id),
                    name=node.name,
                    group_type="subnet",
                    children=[],
                    parent=_group_id("vpc", account_id, region, vpc_id) if vpc_id else None,
                )
            )

        for sg in sgs_resp.get("SecurityGroups", []):
            sg_id = sg["GroupId"]
            tags = _tag_map(sg.get("Tags"))
            vpc_id = sg.get("VpcId", "")
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_security_group",
                resource_id=sg_id,
                name=sg.get("GroupName", sg_id),
                properties={
                    "id": sg_id,
                    "arn": sg.get("GroupArn") or f"arn:aws:ec2:{region}:{account_id}:security-group/{sg_id}",
                    "vpc_id": vpc_id,
                    "description": sg.get("Description"),
                },
                tags=tags,
            )
            nodes.append(node)
            if vpc_id in vpc_nodes:
                pending.append((node.id, vpc_nodes[vpc_id], "in vpc", EdgeType.REFERENCES))

        for reservation in instances_resp.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instance_id = instance["InstanceId"]
                tags = _tag_map(instance.get("Tags"))
                vpc_id = instance.get("VpcId", "")
                subnet_id = instance.get("SubnetId", "")
                node = _build_live_node(
                    account_id=account_id,
                    region=region,
                    resource_type="aws_instance",
                    resource_id=instance_id,
                    name=tags.get("Name", instance_id),
                    properties={
                        "id": instance_id,
                        "arn": f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}",
                        "instance_type": instance.get("InstanceType"),
                        "state": instance.get("State", {}).get("Name"),
                        "vpc_id": vpc_id,
                        "subnet_id": subnet_id,
                        "security_group_ids": [sg["GroupId"] for sg in instance.get("SecurityGroups", [])],
                    },
                    tags=tags,
                )
                nodes.append(node)
                if vpc_id in vpc_nodes:
                    pending.append((node.id, vpc_nodes[vpc_id], "in vpc", EdgeType.REFERENCES))
                if subnet_id:
                    pending.append((node.id, f"arn:aws:ec2:{region}:{account_id}:subnet/{subnet_id}", "in subnet", EdgeType.REFERENCES))

        return nodes, pending, groups

    def _collect_elbv2(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        lbs_resp = {"LoadBalancers": executor.paginate("elbv2", "describe_load_balancers", "LoadBalancers", region=region)}
        tgs_resp = {"TargetGroups": executor.paginate("elbv2", "describe_target_groups", "TargetGroups", region=region)}

        for lb in lbs_resp.get("LoadBalancers", []):
            lb_arn = lb["LoadBalancerArn"]
            lb_name = lb["LoadBalancerName"]
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_lb",
                resource_id=_resource_id_from_arn(lb_arn),
                name=lb_name,
                properties={
                    "id": lb_arn,
                    "arn": lb_arn,
                    "dns_name": lb.get("DNSName"),
                    "vpc_id": lb.get("VpcId"),
                    "subnets": [az.get("SubnetId") for az in lb.get("AvailabilityZones", []) if az.get("SubnetId")],
                    "scheme": lb.get("Scheme"),
                    "type": lb.get("Type"),
                },
            )
            nodes.append(node)
            for subnet_id in node.properties.get("subnets", []):
                pending.append((node.id, f"arn:aws:ec2:{region}:{account_id}:subnet/{subnet_id}", "in subnet", EdgeType.REFERENCES))

            listeners_resp = executor.call("elbv2", "describe_listeners", region=region, LoadBalancerArn=lb_arn) or {}
            for listener in listeners_resp.get("Listeners", []):
                listener_arn = listener["ListenerArn"]
                listener_node = _build_live_node(
                    account_id=account_id,
                    region=region,
                    resource_type="aws_lb_listener",
                    resource_id=_resource_id_from_arn(listener_arn),
                    name=f"{lb_name}:{listener.get('Port')}",
                    properties={
                        "id": listener_arn,
                        "arn": listener_arn,
                        "load_balancer_arn": lb_arn,
                        "port": listener.get("Port"),
                        "protocol": listener.get("Protocol"),
                    },
                )
                nodes.append(listener_node)
                pending.append((listener_node.id, lb_arn, "listens on", EdgeType.REFERENCES))
                for action in listener.get("DefaultActions", []):
                    target_arn = action.get("TargetGroupArn")
                    if target_arn:
                        pending.append((listener_node.id, target_arn, "routes to", EdgeType.ROUTES_TO))

        for tg in tgs_resp.get("TargetGroups", []):
            tg_arn = tg["TargetGroupArn"]
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_lb_target_group",
                resource_id=_resource_id_from_arn(tg_arn),
                name=tg.get("TargetGroupName", _resource_id_from_arn(tg_arn)),
                properties={
                    "id": tg_arn,
                    "arn": tg_arn,
                    "vpc_id": tg.get("VpcId"),
                    "protocol": tg.get("Protocol"),
                    "port": tg.get("Port"),
                    "target_type": tg.get("TargetType"),
                },
            )
            nodes.append(node)
            targets_resp = executor.call_optional(
                "elbv2",
                "describe_target_health",
                region=region,
                swallow_codes={"AccessDeniedException", "TargetGroupNotFound"},
                TargetGroupArn=tg_arn,
            ) or {}
            for desc in targets_resp.get("TargetHealthDescriptions", []):
                target = desc.get("Target", {})
                target_id = target.get("Id")
                if not isinstance(target_id, str) or not target_id:
                    continue
                ref = target_id
                if tg.get("TargetType") == "instance":
                    ref = f"arn:aws:ec2:{region}:{account_id}:instance/{target_id}"
                pending.append(PendingLiveEdge(
                    node.id,
                    ref,
                    "targets",
                    EdgeType.ROUTES_TO,
                    _edge_metadata(
                        "elbv2_target_health",
                        "high",
                        f"Target group contains target {target_id}",
                        "elbv2:describe_target_health",
                    ),
                ))

        return nodes, pending, []

    def _collect_lambda(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType] | PendingLiveEdge] = []
        functions = executor.paginate("lambda", "list_functions", "Functions", region=region)
        for fn in functions:
            arn = fn["FunctionArn"]
            vpc_cfg = fn.get("VpcConfig", {})
            env_vars = fn.get("Environment", {}).get("Variables", {})
            tags_resp = executor.call_optional(
                "lambda",
                "list_tags",
                region=region,
                swallow_codes={"AccessDeniedException", "ResourceNotFoundException"},
                Resource=arn,
            ) or {}
            policy_resp = executor.call_optional(
                "lambda",
                "get_policy",
                region=region,
                swallow_codes={"AccessDeniedException", "ResourceNotFoundException"},
                FunctionName=fn["FunctionName"],
            ) or {}
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_lambda_function",
                resource_id=fn["FunctionName"],
                name=fn["FunctionName"],
                properties={
                    "id": fn["FunctionName"],
                    "function_name": fn["FunctionName"],
                    "arn": arn,
                    "runtime": fn.get("Runtime"),
                    "handler": fn.get("Handler"),
                    "role_arn": fn.get("Role"),
                    "memory_size": fn.get("MemorySize"),
                    "timeout": fn.get("Timeout"),
                    "vpc_id": vpc_cfg.get("VpcId"),
                    "subnet_ids": vpc_cfg.get("SubnetIds", []),
                    "security_group_ids": vpc_cfg.get("SecurityGroupIds", []),
                    "environment": env_vars,
                    "last_modified": fn.get("LastModified"),
                    "resource_policy": policy_resp.get("Policy"),
                },
                tags=tags_resp.get("Tags") if isinstance(tags_resp.get("Tags"), dict) else None,
            )
            nodes.append(node)
            if fn.get("Role"):
                pending.append(PendingLiveEdge(
                    node.id,
                    fn.get("Role"),
                    "assumes role",
                    EdgeType.AUTHENTICATES,
                    _edge_metadata(
                        "lambda_execution_role",
                        "high",
                        f"Lambda configuration role is {fn.get('Role')}",
                        "lambda:list_functions",
                    ),
                ))
            for subnet_id in vpc_cfg.get("SubnetIds", []):
                pending.append((node.id, f"arn:aws:ec2:{region}:{account_id}:subnet/{subnet_id}", "in subnet", EdgeType.REFERENCES))
            if vpc_cfg.get("VpcId"):
                pending.append((node.id, f"arn:aws:ec2:{region}:{account_id}:vpc/{vpc_cfg.get('VpcId')}", "in vpc", EdgeType.REFERENCES))
            for value in env_vars.values():
                if isinstance(value, str) and (value.startswith("arn:") or ".amazonaws.com/" in value):
                    pending.append((node.id, value, "references", EdgeType.REFERENCES))

        mappings = executor.paginate("lambda", "list_event_source_mappings", "EventSourceMappings", region=region)
        for mapping in mappings:
            fn_arn = mapping.get("FunctionArn")
            source_arn = mapping.get("EventSourceArn")
            if fn_arn and source_arn:
                pending.append(
                    PendingLiveEdge(
                        f"aws:{account_id}:{region}:aws_lambda_function:{fn_arn.split(':')[-1]}",
                        source_arn,
                        "reads from",
                        EdgeType.READS_FROM,
                        _edge_metadata(
                            "lambda_event_source_mapping",
                            "high",
                            f"Lambda event source mapping connects {source_arn}",
                            "lambda:list_event_source_mappings",
                        ),
                    )
                )

        return nodes, pending, []

    def _collect_apigateway(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []

        rest = executor.call("apigateway", "get_rest_apis", region=region) or {}
        for api in rest.get("items", []):
            api_id = api["id"]
            api_arn = f"arn:aws:execute-api:{region}:{account_id}:{api_id}"
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_api_gateway_rest_api",
                resource_id=api_id,
                name=api.get("name", api_id),
                properties={
                    "id": api_id,
                    "arn": api_arn,
                    "name": api.get("name"),
                    "description": api.get("description"),
                    "integration_uris": [],
                },
            )
            nodes.append(node)
            resources = executor.call_optional(
                "apigateway",
                "get_resources",
                region=region,
                swallow_codes={"NotFoundException", "BadRequestException"},
                restApiId=api_id,
                limit=500,
            ) or {}
            for resource in resources.get("items", []):
                resource_methods = resource.get("resourceMethods", {}) or {}
                for http_method in resource_methods:
                    integration = executor.call_optional(
                        "apigateway",
                        "get_integration",
                        region=region,
                        swallow_codes={"NotFoundException", "BadRequestException"},
                        restApiId=api_id,
                        resourceId=resource["id"],
                        httpMethod=http_method,
                    ) or {}
                    uri = integration.get("uri")
                    if not uri:
                        continue
                    node.properties.setdefault("integration_uris", []).append(uri)
                    edge_type = EdgeType.TRIGGERS if ":lambda:" in uri else EdgeType.ROUTES_TO
                    inference_rule = (
                        "apigateway_lambda_integration_uri"
                        if ":lambda:" in uri
                        else "apigateway_integration_uri"
                    )
                    pending.append(PendingLiveEdge(
                        node.id,
                        uri,
                        f"{http_method} integration",
                        edge_type,
                        _edge_metadata(
                            inference_rule,
                            "high",
                            f"{http_method} {resource.get('path', '')} integration URI is {uri}",
                            "apigateway:get_integration",
                        ),
                    ))

        v2 = executor.call("apigatewayv2", "get_apis", region=region) or {}
        for api in v2.get("Items", []):
            api_id = api["ApiId"]
            api_arn = f"arn:aws:apigateway:{region}::/apis/{api_id}"
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_apigatewayv2_api",
                resource_id=api_id,
                name=api.get("Name", api_id),
                properties={
                    "id": api_id,
                    "arn": api_arn,
                    "protocol_type": api.get("ProtocolType"),
                    "integration_uris": [],
                },
            )
            nodes.append(node)
            integrations = executor.call("apigatewayv2", "get_integrations", region=region, ApiId=api_id) or {}
            for integration in integrations.get("Items", []):
                uri = integration.get("IntegrationUri")
                if not uri:
                    continue
                node.properties.setdefault("integration_uris", []).append(uri)
                edge_type = EdgeType.TRIGGERS if ":lambda:" in uri else EdgeType.ROUTES_TO
                inference_rule = (
                    "apigateway_lambda_integration_uri"
                    if ":lambda:" in uri
                    else "apigatewayv2_integration_uri"
                )
                pending.append(PendingLiveEdge(
                    node.id,
                    uri,
                    "integration",
                    edge_type,
                    _edge_metadata(
                        inference_rule,
                        "high",
                        f"API Gateway v2 integration URI is {uri}",
                        "apigatewayv2:get_integrations",
                    ),
                ))

        return nodes, pending, []

    def _collect_ecs(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        cluster_arns = executor.paginate("ecs", "list_clusters", "clusterArns", region=region)
        task_defs_seen: set[str] = set()
        for cluster_arn in cluster_arns:
            clusters_resp = executor.call("ecs", "describe_clusters", region=region, clusters=[cluster_arn]) or {}
            for cluster in clusters_resp.get("clusters", []):
                cluster_node = _build_live_node(
                    account_id=account_id,
                    region=region,
                    resource_type="aws_ecs_cluster",
                    resource_id=_resource_id_from_arn(cluster["clusterArn"]),
                    name=cluster["clusterName"],
                    properties={
                        "id": cluster["clusterArn"],
                        "arn": cluster["clusterArn"],
                        "name": cluster["clusterName"],
                    },
                )
                nodes.append(cluster_node)

                service_arns = executor.paginate("ecs", "list_services", "serviceArns", region=region, cluster=cluster["clusterArn"])
                if not service_arns:
                    continue
                services_resp = executor.call("ecs", "describe_services", region=region, cluster=cluster["clusterArn"], services=service_arns) or {}
                for service in services_resp.get("services", []):
                    service_node = _build_live_node(
                        account_id=account_id,
                        region=region,
                        resource_type="aws_ecs_service",
                        resource_id=_resource_id_from_arn(service["serviceArn"]),
                        name=service["serviceName"],
                        properties={
                            "id": service["serviceArn"],
                            "arn": service["serviceArn"],
                            "cluster": cluster["clusterArn"],
                            "task_definition": service.get("taskDefinition"),
                            "target_group_arns": [lb.get("targetGroupArn") for lb in service.get("loadBalancers", []) if lb.get("targetGroupArn")],
                            "subnet_ids": service.get("networkConfiguration", {}).get("awsvpcConfiguration", {}).get("subnets", []),
                            "security_group_ids": service.get("networkConfiguration", {}).get("awsvpcConfiguration", {}).get("securityGroups", []),
                        },
                    )
                    nodes.append(service_node)
                    pending.append((service_node.id, cluster["clusterArn"], "runs on", EdgeType.REFERENCES))
                    if service.get("taskDefinition"):
                        pending.append((service_node.id, service.get("taskDefinition"), "uses task definition", EdgeType.REFERENCES))
                        task_defs_seen.add(service["taskDefinition"])
                    for tg_arn in service_node.properties.get("target_group_arns", []):
                        pending.append((service_node.id, tg_arn, "routes to", EdgeType.ROUTES_TO))

        for task_def_arn in sorted(task_defs_seen):
            td = executor.call("ecs", "describe_task_definition", region=region, taskDefinition=task_def_arn) or {}
            task_def = td.get("taskDefinition")
            if not task_def:
                continue
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_ecs_task_definition",
                resource_id=_resource_id_from_arn(task_def["taskDefinitionArn"]),
                name=task_def.get("family", _resource_id_from_arn(task_def["taskDefinitionArn"])),
                properties={
                    "id": task_def["taskDefinitionArn"],
                    "arn": task_def["taskDefinitionArn"],
                    "family": task_def.get("family"),
                    "task_role_arn": task_def.get("taskRoleArn"),
                    "execution_role_arn": task_def.get("executionRoleArn"),
                },
            )
            nodes.append(node)
            if task_def.get("taskRoleArn"):
                pending.append((node.id, task_def.get("taskRoleArn"), "assumes role", EdgeType.AUTHENTICATES))
            if task_def.get("executionRoleArn"):
                pending.append((node.id, task_def.get("executionRoleArn"), "executes as", EdgeType.AUTHENTICATES))

        return nodes, pending, []

    def _collect_rds(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        dbs = executor.call("rds", "describe_db_instances", region=region) or {}
        for db in dbs.get("DBInstances", []):
            arn = db["DBInstanceArn"]
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_db_instance",
                resource_id=db["DBInstanceIdentifier"],
                name=db["DBInstanceIdentifier"],
                properties={
                    "id": db["DBInstanceIdentifier"],
                    "arn": arn,
                    "engine": db.get("Engine"),
                    "db_name": db.get("DBName"),
                    "vpc_id": db.get("DBSubnetGroup", {}).get("VpcId"),
                    "subnet_ids": [subnet["SubnetIdentifier"] for subnet in db.get("DBSubnetGroup", {}).get("Subnets", [])],
                    "security_group_ids": [group["VpcSecurityGroupId"] for group in db.get("VpcSecurityGroups", []) if group.get("VpcSecurityGroupId")],
                },
            )
            nodes.append(node)
            if node.properties.get("vpc_id"):
                pending.append((node.id, f"arn:aws:ec2:{region}:{account_id}:vpc/{node.properties['vpc_id']}", "in vpc", EdgeType.REFERENCES))

        clusters = executor.call("rds", "describe_db_clusters", region=region) or {}
        for cluster in clusters.get("DBClusters", []):
            arn = cluster["DBClusterArn"]
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_rds_cluster",
                resource_id=cluster["DBClusterIdentifier"],
                name=cluster["DBClusterIdentifier"],
                properties={
                    "id": cluster["DBClusterIdentifier"],
                    "arn": arn,
                    "engine": cluster.get("Engine"),
                },
            )
            nodes.append(node)

        return nodes, pending, []

    def _collect_dynamodb(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        table_names = executor.paginate("dynamodb", "list_tables", "TableNames", region=region)
        for table_name in table_names:
            table_resp = executor.call("dynamodb", "describe_table", region=region, TableName=table_name) or {}
            table = table_resp.get("Table")
            if not table:
                continue
            tags_resp = executor.call_optional(
                "dynamodb",
                "list_tags_of_resource",
                region=region,
                swallow_codes={"AccessDeniedException", "ResourceNotFoundException", "ValidationException"},
                ResourceArn=table["TableArn"],
            ) or {}
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_dynamodb_table",
                resource_id=table_name,
                name=table_name,
                properties={
                    "id": table_name,
                    "name": table_name,
                    "arn": table["TableArn"],
                    "billing_mode": table.get("BillingModeSummary", {}).get("BillingMode"),
                    "hash_key": table.get("KeySchema", [{}])[0].get("AttributeName"),
                    "stream_arn": table.get("LatestStreamArn"),
                },
                tags=_tag_map(tags_resp.get("Tags"), key_name="Key", value_name="Value"),
            )
            nodes.append(node)
        return nodes, [], []

    def _collect_s3(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        buckets_resp = executor.call("s3", "list_buckets", region=region) or {}
        for bucket in buckets_resp.get("Buckets", []):
            bucket_name = bucket["Name"]
            loc_resp = executor.call_optional(
                "s3",
                "get_bucket_location",
                region=region,
                swallow_codes={"AccessDenied", "AccessDeniedException", "NoSuchBucket"},
                Bucket=bucket_name,
            ) or {}
            bucket_region = loc_resp.get("LocationConstraint") or "us-east-1"
            if bucket_region == "EU":
                bucket_region = "eu-west-1"
            tag_resp = executor.call_optional(
                "s3",
                "get_bucket_tagging",
                region=region,
                swallow_codes={"NoSuchTagSet", "NoSuchBucket", "AccessDenied", "AccessDeniedException"},
                Bucket=bucket_name,
            ) or {}
            policy_resp = executor.call_optional(
                "s3",
                "get_bucket_policy",
                region=region,
                swallow_codes={"NoSuchBucketPolicy", "NoSuchBucket", "AccessDenied", "AccessDeniedException"},
                Bucket=bucket_name,
            ) or {}
            node = _build_live_node(
                account_id=account_id,
                region=bucket_region,
                resource_type="aws_s3_bucket",
                resource_id=bucket_name,
                name=bucket_name,
                properties={
                    "id": bucket_name,
                    "bucket": bucket_name,
                    "arn": f"arn:aws:s3:::{bucket_name}",
                    "bucket_domain_name": f"{bucket_name}.s3.amazonaws.com",
                    "bucket_regional_domain_name": f"{bucket_name}.s3.{bucket_region}.amazonaws.com",
                    "creation_date": str(bucket.get("CreationDate")) if bucket.get("CreationDate") else None,
                    "policy": policy_resp.get("Policy"),
                },
                tags=_tag_map(tag_resp.get("TagSet")),
            )
            nodes.append(node)
            if isinstance(node.properties.get("policy"), str):
                self._append_policy_arn_refs(node.id, node.properties["policy"], pending)
        return nodes, pending, []

    def _collect_cloudfront(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        items: list[dict[str, Any]] = []
        resp = executor.call("cloudfront", "list_distributions", region=region) or {}
        dist_list = resp.get("DistributionList", {})
        items.extend(dist_list.get("Items", []))
        while dist_list.get("IsTruncated") and dist_list.get("NextMarker"):
            resp = executor.call("cloudfront", "list_distributions", region=region, Marker=dist_list["NextMarker"]) or {}
            dist_list = resp.get("DistributionList", {})
            items.extend(dist_list.get("Items", []))
        for dist in items:
            arn = dist.get("ARN") or f"arn:aws:cloudfront::{account_id}:distribution/{dist['Id']}"
            node = _build_live_node(
                account_id=account_id,
                region="global",
                resource_type="aws_cloudfront_distribution",
                resource_id=dist["Id"],
                name=dist.get("Aliases", {}).get("Items", [dist["DomainName"]])[0],
                properties={
                    "id": dist["Id"],
                    "arn": arn,
                    "domain_name": dist["DomainName"],
                    "origins": [origin.get("DomainName") for origin in dist.get("Origins", {}).get("Items", [])],
                },
            )
            nodes.append(node)
            for origin in node.properties.get("origins", []):
                pending.append((node.id, origin, "origin", EdgeType.READS_FROM))
        return nodes, pending, []

    def _collect_route53(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType] | PendingLiveEdge] = []
        zones: list[dict[str, Any]] = []
        resp = executor.call("route53", "list_hosted_zones", region=region) or {}
        zones.extend(resp.get("HostedZones", []))
        while resp.get("IsTruncated") and resp.get("NextMarker"):
            resp = executor.call("route53", "list_hosted_zones", region=region, Marker=resp["NextMarker"]) or {}
            zones.extend(resp.get("HostedZones", []))
        for zone in zones:
            zone_id = zone["Id"].split("/")[-1]
            zone_node = _build_live_node(
                account_id=account_id,
                region="global",
                resource_type="aws_route53_zone",
                resource_id=zone_id,
                name=zone["Name"].rstrip("."),
                properties={
                    "id": zone_id,
                    "arn": f"arn:aws:route53:::hostedzone/{zone_id}",
                    "name": zone["Name"].rstrip("."),
                },
            )
            nodes.append(zone_node)
            records = executor.call_optional(
                "route53",
                "list_resource_record_sets",
                region=region,
                swallow_codes={"AccessDenied", "NoSuchHostedZone", "NoSuchHostedZoneException"},
                HostedZoneId=zone["Id"],
            ) or {}
            for record in records.get("ResourceRecordSets", []):
                record_name = str(record.get("Name", "")).rstrip(".")
                record_type = str(record.get("Type", ""))
                values: list[str] = []
                alias_dns = record.get("AliasTarget", {}).get("DNSName")
                if isinstance(alias_dns, str):
                    values.append(alias_dns.rstrip("."))
                for resource_record in record.get("ResourceRecords", []) or []:
                    value = resource_record.get("Value")
                    if isinstance(value, str):
                        values.append(value.rstrip("."))
                if not values:
                    continue
                record_node = _build_live_node(
                    account_id=account_id,
                    region="global",
                    resource_type="aws_route53_record",
                    resource_id=f"{zone_id}:{record_name}:{record_type}",
                    name=f"{record_name} {record_type}",
                    properties={
                        "id": f"{zone_id}:{record_name}:{record_type}",
                        "name": record_name,
                        "type": record_type,
                        "zone_id": zone_id,
                        "targets": values,
                    },
                )
                nodes.append(record_node)
                pending.append(PendingLiveEdge(
                    record_node.id,
                    zone_node.id,
                    "in zone",
                    EdgeType.REFERENCES,
                    _edge_metadata(
                        "route53_record_zone",
                        "high",
                        f"Route53 record belongs to zone {zone_node.name}",
                        "route53:list_resource_record_sets",
                    ),
                ))
                for value in values:
                    pending.append(PendingLiveEdge(
                        record_node.id,
                        value,
                        "routes to",
                        EdgeType.ROUTES_TO,
                        _edge_metadata(
                            "route53_record_target",
                            "high",
                            f"Route53 record target is {value}",
                            "route53:list_resource_record_sets",
                        ),
                    ))
        return nodes, pending, []

    def _collect_sqs(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        queue_urls = executor.paginate("sqs", "list_queues", "QueueUrls", region=region)
        for url in queue_urls:
            attrs = executor.call(
                "sqs",
                "get_queue_attributes",
                region=region,
                QueueUrl=url,
                AttributeNames=["All"],
            ) or {}
            attributes = attrs.get("Attributes", {})
            arn = attributes.get("QueueArn")
            name = url.rsplit("/", 1)[-1]
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_sqs_queue",
                resource_id=name,
                name=name,
                properties={
                    "id": url,
                    "url": url,
                    "arn": arn,
                    "name": name,
                    "policy": attributes.get("Policy"),
                },
            )
            nodes.append(node)
            if isinstance(node.properties.get("policy"), str):
                self._append_policy_arn_refs(node.id, node.properties["policy"], pending)
        return nodes, pending, []

    def _collect_sns(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        topics = executor.paginate("sns", "list_topics", "Topics", region=region)
        for topic in topics:
            arn = topic["TopicArn"]
            attrs = executor.call("sns", "get_topic_attributes", region=region, TopicArn=arn) or {}
            attributes = attrs.get("Attributes", {})
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_sns_topic",
                resource_id=_resource_id_from_arn(arn),
                name=_resource_id_from_arn(arn),
                properties={
                    "id": arn,
                    "arn": arn,
                    "name": _resource_id_from_arn(arn),
                    "policy": attributes.get("Policy"),
                },
            )
            nodes.append(node)
            if isinstance(node.properties.get("policy"), str):
                self._append_policy_arn_refs(node.id, node.properties["policy"], pending)
            subscriptions = executor.call_optional(
                "sns",
                "list_subscriptions_by_topic",
                region=region,
                swallow_codes={"AuthorizationError", "AuthorizationErrorException", "NotFoundException"},
                TopicArn=arn,
            ) or {}
            for subscription in subscriptions.get("Subscriptions", []):
                endpoint = subscription.get("Endpoint")
                protocol = subscription.get("Protocol")
                if not isinstance(endpoint, str):
                    continue
                if not (endpoint.startswith("arn:") or endpoint.startswith("https://")):
                    continue
                edge_type = EdgeType.TRIGGERS if protocol in {"lambda", "sqs"} else EdgeType.ROUTES_TO
                pending.append((node.id, endpoint, "subscription", edge_type))
        return nodes, pending, []

    def _collect_iam(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        roles = executor.paginate("iam", "list_roles", "Roles", region=region)
        for role in roles:
            arn = role["Arn"]
            role_resp = executor.call("iam", "get_role", region=region, RoleName=role["RoleName"]) or {}
            full_role = role_resp.get("Role", role)
            policies: list[dict[str, Any]] = []
            inline_names = executor.paginate(
                "iam",
                "list_role_policies",
                "PolicyNames",
                region=region,
                RoleName=role["RoleName"],
            )
            for policy_name in inline_names:
                policy_resp = executor.call_optional(
                    "iam",
                    "get_role_policy",
                    region=region,
                    swallow_codes={"AccessDenied", "NoSuchEntity", "NoSuchEntityException"},
                    RoleName=role["RoleName"],
                    PolicyName=policy_name,
                ) or {}
                if policy_resp.get("PolicyDocument"):
                    policies.append({
                        "name": policy_name,
                        "type": "inline",
                        "PolicyDocument": policy_resp.get("PolicyDocument"),
                    })

            attached = executor.paginate(
                "iam",
                "list_attached_role_policies",
                "AttachedPolicies",
                region=region,
                RoleName=role["RoleName"],
            )
            for attached_policy in attached:
                policy_arn = attached_policy.get("PolicyArn")
                if not policy_arn:
                    continue
                policy_meta = executor.call_optional(
                    "iam",
                    "get_policy",
                    region=region,
                    swallow_codes={"AccessDenied", "NoSuchEntity", "NoSuchEntityException"},
                    PolicyArn=policy_arn,
                ) or {}
                default_version = policy_meta.get("Policy", {}).get("DefaultVersionId")
                if not default_version:
                    continue
                policy_version = executor.call_optional(
                    "iam",
                    "get_policy_version",
                    region=region,
                    swallow_codes={"AccessDenied", "NoSuchEntity", "NoSuchEntityException"},
                    PolicyArn=policy_arn,
                    VersionId=default_version,
                ) or {}
                document = policy_version.get("PolicyVersion", {}).get("Document")
                if document:
                    policies.append({
                        "name": attached_policy.get("PolicyName") or policy_arn,
                        "arn": policy_arn,
                        "type": "attached",
                        "PolicyDocument": document,
                    })
            node = _build_live_node(
                account_id=account_id,
                region="global",
                resource_type="aws_iam_role",
                resource_id=role["RoleName"],
                name=role["RoleName"],
                properties={
                    "id": role["RoleName"],
                    "arn": arn,
                    "role_name": role["RoleName"],
                    "assume_role_policy": json.dumps(full_role.get("AssumeRolePolicyDocument"), default=str),
                    "policies": policies,
                    "create_date": str(full_role.get("CreateDate")) if full_role.get("CreateDate") else None,
                },
            )
            nodes.append(node)
        return nodes, [], []

    def _collect_elasticache(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        clusters = executor.call("elasticache", "describe_cache_clusters", region=region, ShowCacheNodeInfo=False) or {}
        for cluster in clusters.get("CacheClusters", []):
            arn = cluster.get("ARN") or f"arn:aws:elasticache:{region}:{account_id}:cluster:{cluster['CacheClusterId']}"
            nodes.append(
                _build_live_node(
                    account_id=account_id,
                    region=region,
                    resource_type="aws_elasticache_cluster",
                    resource_id=cluster["CacheClusterId"],
                    name=cluster["CacheClusterId"],
                    properties={
                        "id": cluster["CacheClusterId"],
                        "arn": arn,
                        "engine": cluster.get("Engine"),
                    },
                )
            )
        rep_groups = executor.call("elasticache", "describe_replication_groups", region=region) or {}
        for group in rep_groups.get("ReplicationGroups", []):
            arn = group.get("ARN") or f"arn:aws:elasticache:{region}:{account_id}:replicationgroup:{group['ReplicationGroupId']}"
            nodes.append(
                _build_live_node(
                    account_id=account_id,
                    region=region,
                    resource_type="aws_elasticache_replication_group",
                    resource_id=group["ReplicationGroupId"],
                    name=group["ReplicationGroupId"],
                    properties={
                        "id": group["ReplicationGroupId"],
                        "arn": arn,
                        "status": group.get("Status"),
                    },
                )
            )
        return nodes, [], []

    def _collect_secretsmanager(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        secrets = executor.paginate("secretsmanager", "list_secrets", "SecretList", region=region)
        for secret in secrets:
            nodes.append(
                _build_live_node(
                    account_id=account_id,
                    region=region,
                    resource_type="aws_secretsmanager_secret",
                    resource_id=secret["Name"],
                    name=secret["Name"],
                    properties={
                        "id": secret["Name"],
                        "arn": secret["ARN"],
                        "name": secret["Name"],
                    },
                    tags=_tag_map(secret.get("Tags")),
                )
            )
        return nodes, [], []

    def _collect_eventbridge(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        rules = executor.paginate("events", "list_rules", "Rules", region=region)
        for rule in rules:
            arn = rule["Arn"]
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_cloudwatch_event_rule",
                resource_id=rule["Name"],
                name=rule["Name"],
                properties={
                    "id": rule["Name"],
                    "arn": arn,
                    "event_bus_name": rule.get("EventBusName"),
                },
            )
            nodes.append(node)
            targets = executor.call("events", "list_targets_by_rule", region=region, Rule=rule["Name"], EventBusName=rule.get("EventBusName")) or {}
            for target in targets.get("Targets", []):
                pending.append((node.id, target.get("Arn"), "triggers", EdgeType.TRIGGERS))
        return nodes, pending, []

    def _collect_cognito(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []

        # User Pools
        pools_resp = executor.call("cognito-idp", "list_user_pools", region=region, MaxResults=60) or {}
        for pool_summary in pools_resp.get("UserPools", []):
            pool_id = pool_summary["Id"]
            pool_detail = executor.call_optional(
                "cognito-idp",
                "describe_user_pool",
                region=region,
                swallow_codes={"AccessDeniedException", "ResourceNotFoundException"},
                UserPoolId=pool_id,
            ) or {}
            pool = pool_detail.get("UserPool", pool_summary)
            arn = pool.get("Arn") or f"arn:aws:cognito-idp:{region}:{account_id}:userpool/{pool_id}"
            lambda_config = pool.get("LambdaConfig", {})
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_cognito_user_pool",
                resource_id=pool_id,
                name=pool.get("Name", pool_id),
                properties={
                    "id": pool_id,
                    "arn": arn,
                    "name": pool.get("Name"),
                    "status": pool.get("Status"),
                    "creation_date": str(pool.get("CreationDate")) if pool.get("CreationDate") else None,
                    "lambda_config": lambda_config,
                },
            )
            nodes.append(node)
            # Edges to Lambda triggers
            for trigger_name, trigger_arn in lambda_config.items():
                if isinstance(trigger_arn, str) and trigger_arn.startswith("arn:aws:lambda"):
                    pending.append((node.id, trigger_arn, f"{trigger_name} trigger", EdgeType.TRIGGERS))

            # User Pool Clients
            clients_resp = executor.call_optional(
                "cognito-idp",
                "list_user_pool_clients",
                region=region,
                swallow_codes={"AccessDeniedException", "ResourceNotFoundException"},
                UserPoolId=pool_id,
                MaxResults=60,
            ) or {}
            for client_summary in clients_resp.get("UserPoolClients", []):
                client_id = client_summary["ClientId"]
                client_detail = executor.call_optional(
                    "cognito-idp",
                    "describe_user_pool_client",
                    region=region,
                    swallow_codes={"AccessDeniedException", "ResourceNotFoundException"},
                    UserPoolId=pool_id,
                    ClientId=client_id,
                ) or {}
                client = client_detail.get("UserPoolClient", client_summary)
                client_node = _build_live_node(
                    account_id=account_id,
                    region=region,
                    resource_type="aws_cognito_user_pool_client",
                    resource_id=client_id,
                    name=client.get("ClientName", client_id),
                    properties={
                        "id": client_id,
                        "name": client.get("ClientName"),
                        "user_pool_id": pool_id,
                        "allowed_oauth_flows": client.get("AllowedOAuthFlows", []),
                        "callback_urls": client.get("CallbackURLs", []),
                    },
                )
                nodes.append(client_node)
                pending.append((client_node.id, arn, "belongs to", EdgeType.REFERENCES))

        # Identity Pools
        identity_resp = executor.call_optional(
            "cognito-identity",
            "list_identity_pools",
            region=region,
            swallow_codes={"AccessDeniedException"},
            MaxResults=60,
        ) or {}
        for ip in identity_resp.get("IdentityPools", []):
            ip_id = ip["IdentityPoolId"]
            ip_detail = executor.call_optional(
                "cognito-identity",
                "describe_identity_pool",
                region=region,
                swallow_codes={"AccessDeniedException", "ResourceNotFoundException"},
                IdentityPoolId=ip_id,
            ) or {}
            pool_data = ip_detail if ip_detail else ip
            ip_arn = f"arn:aws:cognito-identity:{region}:{account_id}:identitypool/{ip_id}"
            ip_node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_cognito_identity_pool",
                resource_id=ip_id,
                name=pool_data.get("IdentityPoolName", ip_id),
                properties={
                    "id": ip_id,
                    "arn": ip_arn,
                    "name": pool_data.get("IdentityPoolName"),
                    "allow_unauthenticated": pool_data.get("AllowUnauthenticatedIdentities"),
                },
            )
            nodes.append(ip_node)
            # Link to Cognito User Pool providers
            for provider in pool_data.get("CognitoIdentityProviders", []):
                provider_name = provider.get("ProviderName", "")
                if "cognito-idp" in provider_name:
                    pending.append((ip_node.id, provider_name, "federated from", EdgeType.AUTHENTICATES))

        return nodes, pending, []

    def _collect_stepfunctions(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        from stackmap.parsers.asl import classify_edge_label, parse_asl

        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        machines = executor.paginate("stepfunctions", "list_state_machines", "stateMachines", region=region)
        for sm in machines:
            arn = sm["stateMachineArn"]
            detail = executor.call_optional(
                "stepfunctions",
                "describe_state_machine",
                region=region,
                swallow_codes={"AccessDeniedException", "StateMachineDoesNotExist"},
                stateMachineArn=arn,
            ) or {}
            name = detail.get("name") or sm.get("name", _resource_id_from_arn(arn))
            role_arn = detail.get("roleArn")
            definition = detail.get("definition", "")
            asl_graph = parse_asl(definition) if definition else {"error": "empty"}
            if self.sfn_executions and isinstance(asl_graph, dict) and "error" not in asl_graph:
                asl_graph["recent_executions"] = self._collect_recent_sfn_executions(executor, region, arn)
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_sfn_state_machine",
                resource_id=name,
                name=name,
                properties={
                    "id": name,
                    "arn": arn,
                    "name": name,
                    "type": detail.get("type"),
                    "status": detail.get("status"),
                    "role_arn": role_arn,
                    "creation_date": str(detail.get("creationDate")) if detail.get("creationDate") else None,
                    "asl_graph": asl_graph,
                },
            )
            nodes.append(node)
            if role_arn:
                pending.append((node.id, role_arn, "assumes role", EdgeType.AUTHENTICATES))
            # Emit TRIGGERS edges only for ARNs the ASL parser actually
            # classified as Task targets. Previous regex scan produced
            # false positives from ARNs embedded in Parameters/Credentials.
            for resource in asl_graph.get("resources", []) or []:
                target_arn = resource.get("arn")
                if not target_arn:
                    continue
                label = classify_edge_label(
                    resource.get("kind", "unknown"),
                    resource.get("integration"),
                )
                pending.append((node.id, target_arn, label, EdgeType.TRIGGERS))
        return nodes, pending, []

    def _collect_recent_sfn_executions(
        self,
        executor: AWSAPIExecutor,
        region: str,
        state_machine_arn: str,
    ) -> list[dict[str, Any]]:
        response = executor.call_optional(
            "stepfunctions",
            "list_executions",
            region=region,
            swallow_codes={"AccessDeniedException", "StateMachineDoesNotExist"},
            stateMachineArn=state_machine_arn,
            maxResults=25,
        ) or {}
        executions = response.get("executions", [])
        if not isinstance(executions, list):
            return []
        summaries: list[dict[str, Any]] = []
        for item in executions[:25]:
            start = item.get("startDate")
            stop = item.get("stopDate")
            duration_ms = None
            if start and stop:
                try:
                    duration_ms = int((stop - start).total_seconds() * 1000)
                except Exception:
                    duration_ms = None
            summaries.append({
                "status": item.get("status"),
                "start": start.isoformat() if hasattr(start, "isoformat") else str(start) if start else None,
                "duration_ms": duration_ms,
                "failed_state": None,
            })
        return summaries

    def _collect_ecr(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        repos = executor.paginate("ecr", "describe_repositories", "repositories", region=region)
        for repo in repos:
            arn = repo["repositoryArn"]
            name = repo["repositoryName"]
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_ecr_repository",
                resource_id=name,
                name=name,
                properties={
                    "id": name,
                    "arn": arn,
                    "name": name,
                    "uri": repo.get("repositoryUri"),
                    "created_at": str(repo.get("createdAt")) if repo.get("createdAt") else None,
                    "image_tag_mutability": repo.get("imageTagMutability"),
                    "scan_on_push": repo.get("imageScanningConfiguration", {}).get("scanOnPush"),
                },
            )
            nodes.append(node)
        return nodes, [], []

    def _collect_appsync(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        resp = executor.call("appsync", "list_graphql_apis", region=region) or {}
        for api in resp.get("graphqlApis", []):
            api_id = api["apiId"]
            arn = api.get("arn") or f"arn:aws:appsync:{region}:{account_id}:apis/{api_id}"
            node = _build_live_node(
                account_id=account_id,
                region=region,
                resource_type="aws_appsync_graphql_api",
                resource_id=api_id,
                name=api.get("name", api_id),
                properties={
                    "id": api_id,
                    "arn": arn,
                    "name": api.get("name"),
                    "authentication_type": api.get("authenticationType"),
                    "uris": api.get("uris", {}),
                },
            )
            nodes.append(node)
            # If Cognito auth, link to user pool
            if api.get("authenticationType") == "AMAZON_COGNITO_USER_POOLS":
                user_pool_config = api.get("userPoolConfig", {})
                pool_id = user_pool_config.get("userPoolId")
                if pool_id:
                    pool_arn = f"arn:aws:cognito-idp:{user_pool_config.get('awsRegion', region)}:{account_id}:userpool/{pool_id}"
                    pending.append((node.id, pool_arn, "authenticates via", EdgeType.AUTHENTICATES))

            # Discover data sources
            ds_resp = executor.call_optional(
                "appsync",
                "list_data_sources",
                region=region,
                swallow_codes={"AccessDeniedException", "NotFoundException"},
                apiId=api_id,
            ) or {}
            for ds in ds_resp.get("dataSources", []):
                ds_name = ds["name"]
                ds_type = ds.get("type", "NONE")
                ds_node = _build_live_node(
                    account_id=account_id,
                    region=region,
                    resource_type="aws_appsync_datasource",
                    resource_id=f"{api_id}/{ds_name}",
                    name=ds_name,
                    properties={
                        "id": f"{api_id}/{ds_name}",
                        "name": ds_name,
                        "type": ds_type,
                        "service_role_arn": ds.get("serviceRoleArn"),
                    },
                )
                nodes.append(ds_node)
                pending.append((ds_node.id, arn, "data source for", EdgeType.REFERENCES))
                # Link to backing resource
                if ds_type == "AMAZON_DYNAMODB":
                    table_name = ds.get("dynamodbConfig", {}).get("tableName")
                    if table_name:
                        table_arn = f"arn:aws:dynamodb:{region}:{account_id}:table/{table_name}"
                        pending.append((ds_node.id, table_arn, "reads/writes", EdgeType.READS_FROM))
                elif ds_type == "AWS_LAMBDA":
                    fn_arn = ds.get("lambdaConfig", {}).get("lambdaFunctionArn")
                    if fn_arn:
                        pending.append((ds_node.id, fn_arn, "invokes", EdgeType.TRIGGERS))
                elif ds_type == "HTTP":
                    endpoint = ds.get("httpConfig", {}).get("endpoint")
                    if endpoint:
                        pending.append((ds_node.id, endpoint, "calls", EdgeType.REFERENCES))
                if ds.get("serviceRoleArn"):
                    pending.append((ds_node.id, ds.get("serviceRoleArn"), "assumes role", EdgeType.AUTHENTICATES))

        return nodes, pending, []

    def _collect_tagging(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        executor.call("resourcegroupstaggingapi", "get_resources", region=region, ResourcesPerPage=50)
        return [], [], []

    def _collect_config(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        executor.call("config", "list_discovered_resources", region=region, resourceType="AWS::EC2::VPC")
        return [], [], []

    def _append_policy_arn_refs(
        self,
        source_id: str,
        policy_text: str,
        pending: list[tuple[str, str | None, str, EdgeType]],
    ) -> None:
        try:
            policy = json.loads(policy_text)
        except Exception:
            return
        statements = policy.get("Statement", [])
        if isinstance(statements, dict):
            statements = [statements]
        for statement in statements:
            resources = statement.get("Resource")
            if isinstance(resources, str):
                resources = [resources]
            if isinstance(resources, list):
                for resource in resources:
                    if isinstance(resource, str) and resource.startswith("arn:"):
                        pending.append((source_id, resource.rstrip("*").rstrip("/"), "policy reference", EdgeType.REFERENCES))
