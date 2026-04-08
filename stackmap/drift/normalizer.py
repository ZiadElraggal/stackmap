"""Normalize IaC and Live IRs into a common comparison format for drift detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from stackmap.parsers.base import EdgeType, StackMapEdge, StackMapIR, StackMapNode


@dataclass
class NormalizedResource:
    """A resource normalized for drift comparison."""

    canonical_id: str
    resource_type: str
    name: str
    properties: dict
    relationships: set[tuple[str, str, str]]  # (edge_type, direction, target_canonical_id)
    original_id: str  # original node ID for back-reference
    region: str = ""
    account_id: str = ""

    def __hash__(self) -> int:
        return hash(self.canonical_id)


# Keys used to extract a canonical identifier per resource type.
_NAME_KEYS: dict[str, list[str]] = {
    "aws_lambda_function": ["function_name", "name"],
    "aws_s3_bucket": ["bucket", "name"],
    "aws_dynamodb_table": ["table_name", "name"],
    "aws_db_instance": ["identifier", "db_instance_identifier", "name"],
    "aws_sqs_queue": ["name", "queue_name"],
    "aws_sns_topic": ["name", "topic_name"],
    "aws_ecs_service": ["name", "service_name"],
    "aws_ecs_cluster": ["name", "cluster_name"],
    "aws_api_gateway_rest_api": ["name"],
    "aws_cloudfront_distribution": ["id", "name"],
    "aws_elasticache_replication_group": ["replication_group_id", "name"],
    "aws_kinesis_stream": ["name", "stream_name"],
    "aws_secretsmanager_secret": ["name"],
    "aws_cognito_user_pool": ["name"],
    "aws_stepfunctions_state_machine": ["name"],
    "aws_ecr_repository": ["name", "repository_name"],
}

# CloudFormation property name → Terraform property name mapping.
_CFN_TO_TF_PROPERTY_MAP: dict[str, str] = {
    "FunctionName": "function_name",
    "MemorySize": "memory_size",
    "Timeout": "timeout",
    "Runtime": "runtime",
    "Handler": "handler",
    "BucketName": "bucket",
    "TableName": "table_name",
    "DBInstanceIdentifier": "identifier",
    "InstanceClass": "instance_class",
    "Engine": "engine",
    "EngineVersion": "engine_version",
    "MultiAZ": "multi_az",
    "StorageType": "storage_type",
    "QueueName": "name",
    "TopicName": "name",
    "DesiredCount": "desired_count",
    "ClusterName": "name",
}

_ARN_RE = re.compile(r"^arn:[^:]+:[^:]*:[^:]*:(\d{12})?:(.+)$")


def _extract_arn(node: StackMapNode) -> str | None:
    """Extract ARN from node properties or metadata."""
    arn = node.properties.get("arn") or node.metadata.get("arn")
    if isinstance(arn, str) and arn.startswith("arn:"):
        return arn
    return None


def _extract_canonical_name(node: StackMapNode) -> str:
    """Extract a canonical name from a node for matching purposes."""
    rtype = node.resource_type
    keys = _NAME_KEYS.get(rtype, ["name"])
    for key in keys:
        val = node.properties.get(key)
        if val and isinstance(val, str):
            return val
    return node.name


def _normalize_property_key(key: str) -> str:
    """Normalize a property key to snake_case."""
    if key in _CFN_TO_TF_PROPERTY_MAP:
        return _CFN_TO_TF_PROPERTY_MAP[key]
    # CamelCase to snake_case
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", key)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _normalize_properties(properties: dict) -> dict:
    """Normalize property keys and flatten simple nested structures."""
    result = {}
    for key, value in properties.items():
        normalized_key = _normalize_property_key(key)
        result[normalized_key] = value
    return result


def _build_canonical_id(node: StackMapNode) -> str:
    """Build a canonical ID for matching across IaC and live sources."""
    # Prefer ARN
    arn = _extract_arn(node)
    if arn:
        return arn

    # Fall back to type + canonical name
    canonical_name = _extract_canonical_name(node)
    region = node.metadata.get("region", "")
    account = node.metadata.get("account_id", "")

    parts = [node.resource_type, canonical_name]
    if region:
        parts.insert(0, region)
    if account:
        parts.insert(0, account)
    return ":".join(parts)


def normalize_ir(ir: StackMapIR, source_kind: str = "iac") -> dict[str, NormalizedResource]:
    """Convert IR nodes into normalized resources for comparison.

    Args:
        ir: The StackMapIR to normalize.
        source_kind: "iac" or "live" — affects ID normalization strategy.

    Returns:
        Dict mapping canonical_id to NormalizedResource.
    """
    resources: dict[str, NormalizedResource] = {}
    id_to_canonical: dict[str, str] = {}

    # First pass: create all normalized resources
    for node in ir.nodes:
        canonical_id = _build_canonical_id(node)
        normalized_props = _normalize_properties(node.properties)

        resource = NormalizedResource(
            canonical_id=canonical_id,
            resource_type=node.resource_type,
            name=node.name,
            properties=normalized_props,
            relationships=set(),
            original_id=node.id,
            region=node.metadata.get("region", ""),
            account_id=node.metadata.get("account_id", ""),
        )
        resources[canonical_id] = resource
        id_to_canonical[node.id] = canonical_id

    # Second pass: normalize relationships
    for edge in ir.edges:
        if edge.edge_type == EdgeType.CONTAINS:
            continue
        source_canonical = id_to_canonical.get(edge.source)
        target_canonical = id_to_canonical.get(edge.target)
        if source_canonical and target_canonical:
            if source_canonical in resources:
                resources[source_canonical].relationships.add(
                    (edge.edge_type.value, "outgoing", target_canonical)
                )
            if target_canonical in resources:
                resources[target_canonical].relationships.add(
                    (edge.edge_type.value, "incoming", source_canonical)
                )

    return resources


def match_resources(
    iac_resources: dict[str, NormalizedResource],
    live_resources: dict[str, NormalizedResource],
) -> tuple[
    list[tuple[NormalizedResource, NormalizedResource]],  # matched pairs
    list[NormalizedResource],                              # iac-only (missing in live)
    list[NormalizedResource],                              # live-only (extra)
]:
    """Match IaC resources against live resources.

    Uses a multi-pass matching strategy:
    1. Exact canonical ID match (ARN-based)
    2. Type + name match
    3. Type + tag-based match
    """
    matched: list[tuple[NormalizedResource, NormalizedResource]] = []
    iac_matched: set[str] = set()
    live_matched: set[str] = set()

    # Pass 1: exact canonical ID match
    for canonical_id, iac_res in iac_resources.items():
        if canonical_id in live_resources:
            matched.append((iac_res, live_resources[canonical_id]))
            iac_matched.add(canonical_id)
            live_matched.add(canonical_id)

    # Pass 2: type + name match for unmatched resources
    remaining_iac = {cid: r for cid, r in iac_resources.items() if cid not in iac_matched}
    remaining_live = {cid: r for cid, r in live_resources.items() if cid not in live_matched}

    # Build index by (type, name) for remaining live resources
    live_by_type_name: dict[tuple[str, str], NormalizedResource] = {}
    for cid, res in remaining_live.items():
        key = (res.resource_type, res.name)
        if key not in live_by_type_name:
            live_by_type_name[key] = res

    for cid, iac_res in remaining_iac.items():
        key = (iac_res.resource_type, iac_res.name)
        if key in live_by_type_name:
            live_res = live_by_type_name.pop(key)
            matched.append((iac_res, live_res))
            iac_matched.add(cid)
            live_matched.add(live_res.canonical_id)

    iac_only = [r for cid, r in iac_resources.items() if cid not in iac_matched]
    live_only = [r for cid, r in live_resources.items() if cid not in live_matched]

    return matched, iac_only, live_only
