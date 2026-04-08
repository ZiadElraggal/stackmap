"""Drift detection engine: compare IaC IR against Live IR."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from stackmap.drift.normalizer import NormalizedResource, match_resources, normalize_ir
from stackmap.parsers.base import StackMapIR


class DriftStatus(str, Enum):
    IN_SYNC = "in_sync"
    MISSING_IN_LIVE = "missing"
    EXTRA_IN_LIVE = "extra"
    DRIFTED = "drifted"
    EDGE_MISSING = "edge_missing"
    EDGE_EXTRA = "edge_extra"


# Properties to compare per resource type for drift detection.
DRIFT_PROPERTIES: dict[str, set[str]] = {
    "aws_lambda_function": {
        "runtime", "memory_size", "timeout", "handler",
        "environment", "vpc_config",
    },
    "aws_s3_bucket": {
        "versioning", "server_side_encryption_configuration",
        "public_access_block", "acl",
    },
    "aws_dynamodb_table": {
        "billing_mode", "hash_key", "range_key",
        "global_secondary_indexes",
    },
    "aws_db_instance": {
        "instance_class", "engine", "engine_version",
        "storage_type", "multi_az", "publicly_accessible",
        "storage_encrypted",
    },
    "aws_security_group": {"ingress", "egress"},
    "aws_ecs_service": {"desired_count", "task_definition"},
    "aws_ecs_task_definition": {"cpu", "memory", "network_mode"},
    "aws_sqs_queue": {
        "fifo_queue", "visibility_timeout_seconds", "delay_seconds",
    },
    "aws_sns_topic": {"fifo_topic"},
    "aws_api_gateway_rest_api": {"name", "description"},
    "aws_cloudfront_distribution": {
        "enabled", "default_cache_behavior",
    },
    "aws_elasticache_replication_group": {
        "node_type", "num_node_groups", "num_cache_clusters",
    },
}

_IGNORE_DRIFT_KEYS = frozenset({
    "arn", "id", "last_modified", "created_at", "updated_at",
    "tags_all", "timeouts", "last_updated_date",
})

# Security-critical resource types/fields.
_CRITICAL_TYPES = frozenset({
    "aws_security_group", "aws_iam_role", "aws_iam_policy",
    "aws_iam_user", "aws_iam_group",
})
_CRITICAL_FIELDS = frozenset({
    "ingress", "egress", "policy", "assume_role_policy",
    "publicly_accessible", "public_access_block",
})


@dataclass
class DriftItem:
    resource_id: str
    resource_type: str
    resource_name: str
    status: DriftStatus
    iac_properties: dict | None = None
    live_properties: dict | None = None
    drifted_fields: dict | None = None  # {field: {iac: X, live: Y}}
    severity: str = "info"

    def to_dict(self) -> dict:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "status": self.status.value,
            "iac_properties": self.iac_properties,
            "live_properties": self.live_properties,
            "drifted_fields": self.drifted_fields,
            "severity": self.severity,
        }


@dataclass
class DriftSummary:
    total_iac: int = 0
    total_live: int = 0
    in_sync: int = 0
    missing: int = 0
    extra: int = 0
    drifted: int = 0
    edge_missing: int = 0
    edge_extra: int = 0

    def to_dict(self) -> dict:
        return {
            "total_iac": self.total_iac,
            "total_live": self.total_live,
            "in_sync": self.in_sync,
            "missing": self.missing,
            "extra": self.extra,
            "drifted": self.drifted,
            "edge_missing": self.edge_missing,
            "edge_extra": self.edge_extra,
        }


@dataclass
class DriftReport:
    iac_source: str = ""
    live_source: str = ""
    scanned_at: str = ""
    items: list[DriftItem] = field(default_factory=list)
    edge_drifts: list[DriftItem] = field(default_factory=list)
    summary: DriftSummary = field(default_factory=DriftSummary)

    def to_dict(self) -> dict:
        return {
            "iac_source": self.iac_source,
            "live_source": self.live_source,
            "scanned_at": self.scanned_at,
            "items": [item.to_dict() for item in self.items],
            "edge_drifts": [item.to_dict() for item in self.edge_drifts],
            "summary": self.summary.to_dict(),
        }

    def to_drift_ir(self, base_ir: StackMapIR | None = None) -> StackMapIR:
        """Produce an annotated IR with drift status on each node."""
        from stackmap.parsers.base import StackMapNode

        if base_ir is None:
            return StackMapIR(metadata={"drift_mode": True})

        # Build lookup of drift items by resource name/type
        drift_lookup: dict[str, DriftItem] = {}
        for item in self.items:
            drift_lookup[item.resource_id] = item

        annotated_nodes: list[StackMapNode] = []
        for node in base_ir.nodes:
            drift_item = drift_lookup.get(node.id)
            position_hint = dict(node.position_hint)
            if drift_item:
                position_hint["drift_status"] = drift_item.status.value
                position_hint["drift_severity"] = drift_item.severity
                if drift_item.drifted_fields:
                    position_hint["drift_fields"] = drift_item.drifted_fields
            else:
                position_hint["drift_status"] = "in_sync"

            annotated_nodes.append(
                StackMapNode(
                    id=node.id,
                    name=node.name,
                    resource_type=node.resource_type,
                    provider=node.provider,
                    category=node.category,
                    properties=node.properties,
                    tags=node.tags,
                    metadata=node.metadata,
                    position_hint=position_hint,
                )
            )

        metadata = {
            **base_ir.metadata,
            "drift_mode": True,
            "drift_summary": self.summary.to_dict(),
            "iac_source": self.iac_source,
            "live_scanned_at": self.scanned_at,
        }

        return StackMapIR(
            metadata=metadata,
            nodes=annotated_nodes,
            edges=list(base_ir.edges),
            groups=list(base_ir.groups),
        )


def _classify_severity(
    resource_type: str,
    status: DriftStatus,
    drifted_fields: dict | None,
) -> str:
    """Classify drift severity based on resource type and drifted fields."""
    if status == DriftStatus.IN_SYNC:
        return "info"

    if status == DriftStatus.MISSING_IN_LIVE:
        if resource_type in _CRITICAL_TYPES:
            return "critical"
        return "warning"

    if status == DriftStatus.EXTRA_IN_LIVE:
        if resource_type in _CRITICAL_TYPES:
            return "warning"
        return "info"

    if status == DriftStatus.DRIFTED and drifted_fields:
        for field_name in drifted_fields:
            if field_name in _CRITICAL_FIELDS:
                return "critical"
        if resource_type in _CRITICAL_TYPES:
            return "critical"
        return "warning"

    return "info"


def _compare_resource_properties(
    iac_res: NormalizedResource,
    live_res: NormalizedResource,
) -> dict | None:
    """Compare properties of matched resources, return drifted fields or None."""
    resource_type = iac_res.resource_type
    keys_to_check = DRIFT_PROPERTIES.get(resource_type)

    iac_props = iac_res.properties
    live_props = live_res.properties

    if keys_to_check is None:
        keys_to_check = (set(iac_props.keys()) | set(live_props.keys())) - _IGNORE_DRIFT_KEYS

    drifted: dict = {}
    for key in keys_to_check:
        iac_val = iac_props.get(key)
        live_val = live_props.get(key)
        # Skip if both are None/empty
        if iac_val is None and live_val is None:
            continue
        if iac_val != live_val:
            drifted[key] = {"iac": iac_val, "live": live_val}

    return drifted if drifted else None


def _compare_edges(
    iac_res: NormalizedResource,
    live_res: NormalizedResource,
) -> tuple[list[DriftItem], int, int]:
    """Compare relationships between matched resources."""
    iac_rels = iac_res.relationships
    live_rels = live_res.relationships

    missing_rels = iac_rels - live_rels
    extra_rels = live_rels - iac_rels

    edge_drifts: list[DriftItem] = []
    for rel in missing_rels:
        edge_drifts.append(DriftItem(
            resource_id=f"{iac_res.original_id}:{rel[2]}",
            resource_type=iac_res.resource_type,
            resource_name=f"{iac_res.name} -> {rel[2]}",
            status=DriftStatus.EDGE_MISSING,
            severity="warning",
        ))
    for rel in extra_rels:
        edge_drifts.append(DriftItem(
            resource_id=f"{live_res.original_id}:{rel[2]}",
            resource_type=live_res.resource_type,
            resource_name=f"{live_res.name} -> {rel[2]}",
            status=DriftStatus.EDGE_EXTRA,
            severity="info",
        ))

    return edge_drifts, len(missing_rels), len(extra_rels)


def compute_drift(iac_ir: StackMapIR, live_ir: StackMapIR) -> DriftReport:
    """Compare IaC IR against Live IR and produce a drift report.

    Args:
        iac_ir: Infrastructure-as-code IR (from Terraform state, CFN, etc.).
        live_ir: Live infrastructure IR (from scan-aws or similar).

    Returns:
        DriftReport with all drift items and summary statistics.
    """
    iac_resources = normalize_ir(iac_ir, source_kind="iac")
    live_resources = normalize_ir(live_ir, source_kind="live")

    matched, iac_only, live_only = match_resources(iac_resources, live_resources)

    items: list[DriftItem] = []
    edge_drifts: list[DriftItem] = []
    summary = DriftSummary(
        total_iac=len(iac_resources),
        total_live=len(live_resources),
    )

    # Process matched pairs
    for iac_res, live_res in matched:
        drifted_fields = _compare_resource_properties(iac_res, live_res)

        if drifted_fields:
            status = DriftStatus.DRIFTED
            severity = _classify_severity(iac_res.resource_type, status, drifted_fields)
            summary.drifted += 1
        else:
            status = DriftStatus.IN_SYNC
            severity = "info"
            summary.in_sync += 1

        items.append(DriftItem(
            resource_id=iac_res.original_id,
            resource_type=iac_res.resource_type,
            resource_name=iac_res.name,
            status=status,
            iac_properties=iac_res.properties,
            live_properties=live_res.properties,
            drifted_fields=drifted_fields,
            severity=severity,
        ))

        # Compare edges for matched pairs
        pair_edge_drifts, edge_missing, edge_extra = _compare_edges(iac_res, live_res)
        edge_drifts.extend(pair_edge_drifts)
        summary.edge_missing += edge_missing
        summary.edge_extra += edge_extra

    # Process IaC-only (missing in live)
    for iac_res in iac_only:
        status = DriftStatus.MISSING_IN_LIVE
        severity = _classify_severity(iac_res.resource_type, status, None)
        summary.missing += 1
        items.append(DriftItem(
            resource_id=iac_res.original_id,
            resource_type=iac_res.resource_type,
            resource_name=iac_res.name,
            status=status,
            iac_properties=iac_res.properties,
            severity=severity,
        ))

    # Process live-only (extra in live)
    for live_res in live_only:
        status = DriftStatus.EXTRA_IN_LIVE
        severity = _classify_severity(live_res.resource_type, status, None)
        summary.extra += 1
        items.append(DriftItem(
            resource_id=live_res.original_id,
            resource_type=live_res.resource_type,
            resource_name=live_res.name,
            status=status,
            live_properties=live_res.properties,
            severity=severity,
        ))

    return DriftReport(
        iac_source=iac_ir.metadata.get("source_path", ""),
        live_source=live_ir.metadata.get("source_path", ""),
        scanned_at=datetime.now(UTC).isoformat(),
        items=items,
        edge_drifts=edge_drifts,
        summary=summary,
    )
