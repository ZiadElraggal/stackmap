"""Read-only live AWS account scanning."""

from __future__ import annotations

import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from stackmap.organizations import (
    OrganizationDocument,
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
]
POLICY_ACTIONS_BROAD = POLICY_ACTIONS_CORE + [
    "elasticache:Describe*",
    "secretsmanager:ListSecrets",
    "events:ListRules",
    "events:ListTargetsByRule",
    "tag:GetResources",
    "config:ListDiscoveredResources",
    "config:BatchGetResourceConfig",
]


def build_policy_document(service_set: str = "broad") -> dict[str, Any]:
    actions = POLICY_ACTIONS_CORE if service_set == "core" else POLICY_ACTIONS_BROAD
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
        cache_dir: str | None = None,
        no_cache: bool = False,
        partial_write_path: str | None = None,
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
        self.cache_dir = None if no_cache else Path(cache_dir or "~/.stackmap/cache").expanduser()
        self.partial_write_path = Path(partial_write_path) if partial_write_path else None
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
            org = load_organization_document(self.org_file or "")
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
        if not self.org_file:
            raise ValueError("--org-scan requires --org-file")
        org = load_organization_document(self.org_file)
        base_session, auth_description = self._resolve_base_session()
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
            try:
                session = self._assume_role(base_session, role_arn)
                context = AccountScanContext(
                    session=session,
                    account_id=account["id"],
                    account_name=account.get("name"),
                    auth_description=auth_description,
                    role_arn=role_arn,
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
                failure_ir = None
                merged.metadata["errors"].append(f"{account['id']}: {exc}")
                return account, failure_ir

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
        for region in context.regions:
            for service in sorted(context.services):
                self._collect_service(service, region, executor, plan_only=True)

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
                try:
                    service_nodes, service_pending, service_groups = self._collect_service(service, region, executor)
                    regional_nodes.extend(service_nodes)
                    regional_pending_edges.extend(service_pending)
                    regional_groups.extend(service_groups)
                except Exception as exc:
                    regional_errors.append(f"{context.account_id}:{region}:{service}: {exc}")
            return regional_nodes, regional_pending_edges, regional_groups, regional_warnings, regional_errors

        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(context.regions))) as pool:
            futures = {pool.submit(scan_region, region): region for region in context.regions}
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
        pending_edges: list[tuple[str, str | None, str, EdgeType]],
        groups: list[StackMapGroup],
    ) -> StackMapIR:
        node_by_id = {node.id: node for node in nodes}
        arn_index: dict[str, str] = {}
        id_index: dict[str, str] = {}
        bucket_name_index: dict[str, str] = {}
        dns_index: dict[str, str] = {}

        for node in nodes:
            if isinstance(node.properties.get("arn"), str):
                arn_index[str(node.properties["arn"])] = node.id
            for key in ("id", "name", "function_name", "bucket", "url", "domain_name", "dns_name"):
                value = node.properties.get(key)
                if isinstance(value, str) and value:
                    id_index[value] = node.id
            if node.resource_type == "aws_s3_bucket" and isinstance(node.properties.get("bucket"), str):
                bucket_name = str(node.properties["bucket"])
                bucket_name_index[bucket_name] = node.id
                bucket_name_index[f"{bucket_name}.s3.amazonaws.com"] = node.id
                region = str(node.metadata.get("region") or "")
                if region:
                    bucket_name_index[f"{bucket_name}.s3.{region}.amazonaws.com"] = node.id
            if isinstance(node.properties.get("dns_name"), str):
                dns_index[str(node.properties["dns_name"])] = node.id

        edges: list[StackMapEdge] = []
        seen: set[tuple[str, str, str]] = set()
        for source_id, target_ref, label, edge_type in pending_edges:
            if source_id not in node_by_id or not target_ref:
                continue
            target_id = (
                arn_index.get(target_ref)
                or id_index.get(target_ref)
                or bucket_name_index.get(target_ref)
                or dns_index.get(target_ref)
            )
            if not target_id or target_id == source_id:
                continue
            key = (source_id, target_id, edge_type.value)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                StackMapEdge(
                    id=f"{source_id}->{target_id}:{edge_type.value}",
                    source=source_id,
                    target=target_id,
                    edge_type=edge_type,
                    label=label,
                )
            )

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
            groups=groups,
        )
        overlay_organization_groups(ir, org=load_organization_document(self.org_file) if self.org_file else None, strict=False)
        infer_cross_account_edges(ir)
        return ir

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
        lbs_resp = executor.call("elbv2", "describe_load_balancers", region=region) or {}
        tgs_resp = executor.call("elbv2", "describe_target_groups", region=region) or {}

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

        return nodes, pending, []

    def _collect_lambda(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        functions = executor.paginate("lambda", "list_functions", "Functions", region=region)
        for fn in functions:
            arn = fn["FunctionArn"]
            vpc_cfg = fn.get("VpcConfig", {})
            env_vars = fn.get("Environment", {}).get("Variables", {})
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
                },
            )
            nodes.append(node)
            if fn.get("Role"):
                pending.append((node.id, fn.get("Role"), "assumes role", EdgeType.AUTHENTICATES))
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
                    (
                        f"aws:{account_id}:{region}:aws_lambda_function:{fn_arn.split(':')[-1]}",
                        source_arn,
                        "reads from",
                        EdgeType.READS_FROM,
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
                },
            )
            nodes.append(node)

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
                },
            )
            nodes.append(node)
            integrations = executor.call("apigatewayv2", "get_integrations", region=region, ApiId=api_id) or {}
            for integration in integrations.get("Items", []):
                uri = integration.get("IntegrationUri")
                if not uri:
                    continue
                edge_type = EdgeType.TRIGGERS if ":lambda:" in uri else EdgeType.ROUTES_TO
                pending.append((node.id, uri, "integration", edge_type))

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
            tags_resp = executor.call("dynamodb", "list_tags_of_resource", region=region, ResourceArn=table["TableArn"]) or {}
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
            loc_resp = executor.call("s3", "get_bucket_location", region=region, Bucket=bucket_name) or {}
            bucket_region = loc_resp.get("LocationConstraint") or "us-east-1"
            if bucket_region != region:
                continue
            tag_resp = executor.call("s3", "get_bucket_tagging", region=region, Bucket=bucket_name) or {}
            policy_resp = executor.call("s3", "get_bucket_policy", region=region, Bucket=bucket_name) or {}
            node = _build_live_node(
                account_id=account_id,
                region=region,
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
        resp = executor.call("cloudfront", "list_distributions", region=region) or {}
        items = resp.get("DistributionList", {}).get("Items", [])
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
        resp = executor.call("route53", "list_hosted_zones", region=region) or {}
        for zone in resp.get("HostedZones", []):
            zone_id = zone["Id"].split("/")[-1]
            nodes.append(
                _build_live_node(
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
            )
        return nodes, [], []

    def _collect_sqs(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        pending: list[tuple[str, str | None, str, EdgeType]] = []
        resp = executor.call("sqs", "list_queues", region=region) or {}
        for url in resp.get("QueueUrls", []):
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
        return nodes, pending, []

    def _collect_iam(self, region: str, executor: AWSAPIExecutor) -> tuple[list[StackMapNode], list[tuple[str, str | None, str, EdgeType]], list[StackMapGroup]]:
        account_id = executor.context.account_id
        nodes: list[StackMapNode] = []
        roles = executor.paginate("iam", "list_roles", "Roles", region=region)
        for role in roles:
            arn = role["Arn"]
            role_resp = executor.call("iam", "get_role", region=region, RoleName=role["RoleName"]) or {}
            full_role = role_resp.get("Role", role)
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
        resp = executor.call("secretsmanager", "list_secrets", region=region) or {}
        for secret in resp.get("SecretList", []):
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
        resp = executor.call("events", "list_rules", region=region) or {}
        for rule in resp.get("Rules", []):
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
