"""Cost estimation engine: estimate monthly costs for infrastructure resources."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from stackmap.parsers.base import StackMapIR, StackMapNode


_PRICING_DB: dict | None = None
_RESOURCE_TYPE_ALIASES = {
    "AWS::Lambda::Function": "aws_lambda_function",
    "AWS::Serverless::Function": "aws_lambda_function",
    "AWS::ApiGateway::RestApi": "aws_api_gateway_rest_api",
    "AWS::Serverless::Api": "aws_api_gateway_rest_api",
    "AWS::DynamoDB::Table": "aws_dynamodb_table",
    "AWS::S3::Bucket": "aws_s3_bucket",
    "AWS::CloudFront::Distribution": "aws_cloudfront_distribution",
    "AWS::EC2::NatGateway": "aws_nat_gateway",
    "AWS::ECS::Service": "aws_ecs_service",
    "AWS::RDS::DBInstance": "aws_db_instance",
    "AWS::RDS::DBCluster": "aws_rds_cluster",
    "AWS::SQS::Queue": "aws_sqs_queue",
    "AWS::SNS::Topic": "aws_sns_topic",
}


def _load_pricing_db() -> dict:
    """Load the embedded pricing database."""
    global _PRICING_DB
    if _PRICING_DB is None:
        db_path = Path(__file__).parent / "pricing_db.json"
        with open(db_path) as f:
            _PRICING_DB = json.load(f)
    return _PRICING_DB


def _pricing_resource_type(resource_type: str) -> str:
    return _RESOURCE_TYPE_ALIASES.get(resource_type, resource_type)


@dataclass
class CostEstimate:
    resource_id: str
    resource_name: str
    resource_type: str
    monthly_estimate: float
    confidence: str  # "high", "medium", "low", "unknown"
    pricing_model: str
    estimate_note: str
    breakdown: dict | None = None

    def to_dict(self) -> dict:
        anomaly = (self.breakdown or {}).get("anomaly") if isinstance(self.breakdown, dict) else None
        monthly_actual = (self.breakdown or {}).get("monthly_actual") if isinstance(self.breakdown, dict) else None
        payload = {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "monthly_estimate": round(self.monthly_estimate, 2),
            "confidence": self.confidence,
            "pricing_model": self.pricing_model,
            "estimate_note": self.estimate_note,
            "breakdown": self.breakdown,
        }
        if monthly_actual is not None:
            payload["monthly_actual"] = monthly_actual
        if anomaly is not None:
            payload["anomaly"] = anomaly
        return payload


@dataclass
class CostReport:
    total_monthly: float = 0.0
    by_node: dict[str, CostEstimate] = field(default_factory=dict)
    by_group: dict[str, float] = field(default_factory=dict)
    by_category: dict[str, float] = field(default_factory=dict)
    by_tier: dict[str, float] = field(default_factory=dict)
    expensive_paths: list[dict] = field(default_factory=list)
    currency: str = "USD"

    def to_dict(self) -> dict:
        return {
            "total_monthly": round(self.total_monthly, 2),
            "by_node": {k: v.to_dict() for k, v in self.by_node.items()},
            "by_group": {k: round(v, 2) for k, v in self.by_group.items()},
            "by_category": {k: round(v, 2) for k, v in self.by_category.items()},
            "by_tier": {k: round(v, 2) for k, v in self.by_tier.items()},
            "expensive_paths": self.expensive_paths,
            "currency": self.currency,
        }


def _estimate_lambda(node: StackMapNode, service_config: dict, override: dict | None = None) -> CostEstimate:
    """Estimate Lambda cost based on memory_size tier.

    Override keys:
    - memory_mb: memory in MB (default: from properties or 256)
    - invocations_per_month: invocation count (default: 1_000_000)
    - avg_duration_ms: average execution time in ms (default: 200)
    """
    override = override or {}
    memory = override.get("memory_mb") or node.properties.get("memory_size", 256)
    tiers = service_config.get("tiers", {})

    # Find closest tier
    if isinstance(memory, (int, float)):
        memory_str = str(int(memory))
    else:
        memory_str = str(memory)

    if memory_str in tiers:
        base_cost = tiers[memory_str]
        confidence = "medium" if override else "medium"
    else:
        tier_vals = sorted(int(k) for k in tiers)
        mem_int = int(memory) if isinstance(memory, (int, float)) else 256
        closest = min(tier_vals, key=lambda x: abs(x - mem_int))
        base_cost = tiers[str(closest)]
        confidence = "low"

    # Tier prices assume ~1M invocations/month at 200ms.
    # Scale linearly when user provides actual usage.
    invocations = override.get("invocations_per_month")
    duration = override.get("avg_duration_ms")
    if invocations is not None or duration is not None:
        inv_actual = invocations if invocations is not None else 1_000_000
        dur_actual = duration if duration is not None else 200
        inv_scale = inv_actual / 1_000_000 if inv_actual > 0 else 0
        dur_scale = dur_actual / 200 if dur_actual > 0 else 0
        cost = base_cost * inv_scale * dur_scale
        confidence = "high"
        note = (
            f"{memory}MB, {int(inv_actual):,} invocations/month, "
            f"{int(dur_actual)}ms avg"
        )
    else:
        cost = base_cost
        note = f"{memory}MB, ~1M invocations/month estimate"

    return CostEstimate(
        resource_id=node.id,
        resource_name=node.name,
        resource_type=node.resource_type,
        monthly_estimate=cost,
        confidence=confidence,
        pricing_model="invocation",
        estimate_note=note,
    )


def _estimate_instance_based(node: StackMapNode, service_config: dict) -> CostEstimate:
    """Estimate cost for instance-based services (RDS, ElastiCache)."""
    estimate_key = service_config.get("estimate_key", "instance_class")
    instance_type = node.properties.get(estimate_key, "")
    instance_costs = service_config.get("instance_costs", {})
    default_cost = service_config.get("default_cost", 0)

    if instance_type and instance_type in instance_costs:
        cost = instance_costs[instance_type]
        confidence = "high"
        note = f"Instance type: {instance_type}"
    elif instance_type:
        cost = default_cost
        confidence = "low"
        note = f"Instance type {instance_type} not in pricing DB, using default"
    else:
        cost = default_cost
        confidence = "low"
        note = "No instance type specified, using default estimate"

    # Multi-AZ multiplier for RDS
    if node.resource_type in ("aws_db_instance", "aws_rds_cluster"):
        multi_az = node.properties.get("multi_az", False)
        multiplier = service_config.get("multi_az_multiplier", 1.0)
        if multi_az:
            cost *= multiplier
            note += f", multi-AZ (x{multiplier})"

    return CostEstimate(
        resource_id=node.id,
        resource_name=node.name,
        resource_type=node.resource_type,
        monthly_estimate=cost,
        confidence=confidence,
        pricing_model="instance",
        estimate_note=note,
    )


def _estimate_dynamodb(node: StackMapNode, service_config: dict) -> CostEstimate:
    """Estimate DynamoDB cost based on billing_mode."""
    billing_mode = node.properties.get("billing_mode", "PAY_PER_REQUEST")

    if billing_mode == "PROVISIONED":
        cost = service_config.get("provisioned_base", 25.0)
        confidence = "medium"
        note = "Provisioned mode, base estimate"
    else:
        cost = service_config.get("on_demand_base", 1.25)
        confidence = "medium"
        note = "On-demand mode, base estimate"

    return CostEstimate(
        resource_id=node.id,
        resource_name=node.name,
        resource_type=node.resource_type,
        monthly_estimate=cost,
        confidence=confidence,
        pricing_model="capacity",
        estimate_note=note,
    )


def _estimate_ecs(node: StackMapNode, service_config: dict) -> CostEstimate:
    """Estimate ECS/Fargate cost."""
    cpu = node.properties.get("cpu", 256)
    memory = node.properties.get("memory", 512)
    desired_count = node.properties.get("desired_count", 1)

    if isinstance(cpu, (int, float)) and isinstance(memory, (int, float)):
        vcpu = cpu / 1024
        gb = memory / 1024
        per_vcpu_hour = service_config.get("per_vcpu_hour", 0.04048)
        per_gb_hour = service_config.get("per_gb_hour", 0.004445)
        hours = 730  # avg hours/month
        cost = (vcpu * per_vcpu_hour + gb * per_gb_hour) * hours * (desired_count if isinstance(desired_count, (int, float)) else 1)
        confidence = "medium"
        note = f"Fargate: {vcpu} vCPU, {gb}GB, {desired_count} tasks"
    else:
        cost = service_config.get("default_monthly", 36.0)
        confidence = "low"
        note = "Default Fargate estimate"

    return CostEstimate(
        resource_id=node.id,
        resource_name=node.name,
        resource_type=node.resource_type,
        monthly_estimate=cost,
        confidence=confidence,
        pricing_model="fargate",
        estimate_note=note,
    )


def _estimate_generic(node: StackMapNode, service_config: dict, override: dict | None = None) -> CostEstimate:
    """Generic cost estimate.

    Honors override keys:
    - storage_gb: scales 'per_gb_monthly' pricing (S3, EBS, EFS, etc.)
    - data_transfer_gb: scales 'per_gb_transfer' pricing (CloudFront, NAT GW)
    """
    override = override or {}
    pricing_model = service_config.get("pricing_model", "unknown")
    notes = service_config.get("notes", "")
    base_cost = service_config.get("base_monthly", 0) or service_config.get("default_monthly", 0)
    cost = base_cost

    storage_gb = override.get("storage_gb")
    transfer_gb = override.get("data_transfer_gb")
    note_extras: list[str] = []

    per_gb = service_config.get("per_gb_monthly")
    if per_gb is not None and storage_gb is not None:
        # Replace base cost component for storage rather than adding to it
        default_storage_gb = service_config.get("default_gb")
        if isinstance(default_storage_gb, (int, float)) and default_storage_gb > 0:
            cost += per_gb * (storage_gb - default_storage_gb)
        else:
            cost = per_gb * storage_gb
        note_extras.append(f"{storage_gb}GB storage")

    per_gb_transfer = service_config.get("per_gb_transfer") or service_config.get("per_gb_processed")
    if per_gb_transfer is not None and transfer_gb is not None:
        default_transfer_gb = service_config.get("default_transfer_gb")
        if isinstance(default_transfer_gb, (int, float)) and default_transfer_gb > 0:
            cost += per_gb_transfer * (transfer_gb - default_transfer_gb)
        else:
            cost += per_gb_transfer * transfer_gb
        note_extras.append(f"{transfer_gb}GB transfer")

    if note_extras:
        confidence = "high"
    elif pricing_model == "reference":
        confidence = "high"  # We know it's $0
    elif cost > 0:
        confidence = "low"
    else:
        confidence = "unknown"

    if note_extras:
        note = ", ".join(note_extras)
    else:
        note = notes or f"Estimate based on {pricing_model} pricing"

    return CostEstimate(
        resource_id=node.id,
        resource_name=node.name,
        resource_type=node.resource_type,
        monthly_estimate=cost,
        confidence=confidence,
        pricing_model=pricing_model,
        estimate_note=note,
    )


def _estimate_node_cost(
    node: StackMapNode,
    pricing_db: dict,
    override: dict | None = None,
) -> CostEstimate:
    """Estimate cost for a single node, optionally with usage overrides."""
    services = pricing_db.get("services", {})
    pricing_resource_type = _pricing_resource_type(node.resource_type)
    service_config = services.get(pricing_resource_type)

    if service_config is None:
        return CostEstimate(
            resource_id=node.id,
            resource_name=node.name,
            resource_type=node.resource_type,
            monthly_estimate=0,
            confidence="unknown",
            pricing_model="unknown",
            estimate_note=f"No pricing data for {node.resource_type}",
        )

    pricing_model = service_config.get("pricing_model", "")

    if pricing_resource_type == "aws_lambda_function":
        return _estimate_lambda(node, service_config, override)

    if pricing_resource_type == "aws_dynamodb_table":
        return _estimate_dynamodb(node, service_config)

    if pricing_resource_type in ("aws_ecs_service",):
        return _estimate_ecs(node, service_config)

    if pricing_model == "instance" and "instance_costs" in service_config:
        return _estimate_instance_based(node, service_config)

    return _estimate_generic(node, service_config, override)


def _find_expensive_paths(
    ir: StackMapIR,
    costs: dict[str, CostEstimate],
) -> list[dict]:
    """Find the top 5 most expensive connected paths through the graph."""
    from stackmap.parsers.base import EdgeType

    paths: list[dict] = []
    for edge in ir.edges:
        if edge.edge_type == EdgeType.CONTAINS:
            continue
        source_cost = costs.get(edge.source)
        target_cost = costs.get(edge.target)
        if source_cost and target_cost:
            total = source_cost.monthly_estimate + target_cost.monthly_estimate
            if total > 0:
                paths.append({
                    "source": edge.source,
                    "target": edge.target,
                    "edge_type": edge.edge_type.value,
                    "total_cost": round(total, 2),
                    "source_cost": round(source_cost.monthly_estimate, 2),
                    "target_cost": round(target_cost.monthly_estimate, 2),
                })

    paths.sort(key=lambda x: -x["total_cost"])
    return paths[:5]


def estimate_costs(
    ir: StackMapIR,
    overrides: dict[str, dict] | None = None,
) -> CostReport:
    """Estimate costs for all resources in the IR.

    Args:
        ir: parsed infrastructure IR.
        overrides: optional mapping of node_id -> usage override dict.
            Supported keys per node:
            - Lambda: memory_mb, invocations_per_month, avg_duration_ms
            - Storage/transfer: storage_gb, data_transfer_gb

    Returns a CostReport with per-node, per-category, and per-tier breakdowns.
    """
    pricing_db = _load_pricing_db()
    overrides = overrides or {}
    by_node: dict[str, CostEstimate] = {}
    by_category: dict[str, float] = {}
    by_tier: dict[str, float] = {}

    for node in ir.nodes:
        estimate = _estimate_node_cost(node, pricing_db, overrides.get(node.id))
        by_node[node.id] = estimate

        # Aggregate by category
        cat = node.category.value if hasattr(node.category, "value") else str(node.category)
        by_category[cat] = by_category.get(cat, 0) + estimate.monthly_estimate

        # Aggregate by tier (from position_hint)
        tier = node.position_hint.get("tier", "other")
        by_tier[tier] = by_tier.get(tier, 0) + estimate.monthly_estimate

    total = sum(e.monthly_estimate for e in by_node.values())

    # Group costs
    by_group: dict[str, float] = {}
    group_children: dict[str, list[str]] = {}
    for group in ir.groups:
        group_children[group.id] = group.children

    for group_id, children in group_children.items():
        group_total = sum(
            by_node[nid].monthly_estimate for nid in children if nid in by_node
        )
        by_group[group_id] = group_total

    expensive_paths = _find_expensive_paths(ir, by_node)

    return CostReport(
        total_monthly=total,
        by_node=by_node,
        by_group=by_group,
        by_category=by_category,
        by_tier=by_tier,
        expensive_paths=expensive_paths,
    )


def annotate_ir_with_costs(
    ir: StackMapIR,
    overrides: dict[str, dict] | None = None,
) -> StackMapIR:
    """Return a new IR with cost annotations in node position_hints and metadata."""
    report = estimate_costs(ir, overrides=overrides)

    annotated_nodes = []
    for node in ir.nodes:
        estimate = report.by_node.get(node.id)
        position_hint = dict(node.position_hint)
        if estimate:
            position_hint["cost_monthly"] = round(estimate.monthly_estimate, 2)
            position_hint["cost_confidence"] = estimate.confidence
            position_hint["cost_note"] = estimate.estimate_note

        annotated_nodes.append(StackMapNode(
            id=node.id,
            name=node.name,
            resource_type=node.resource_type,
            provider=node.provider,
            category=node.category,
            properties=node.properties,
            tags=node.tags,
            metadata=node.metadata,
            position_hint=position_hint,
        ))

    metadata = dict(ir.metadata)
    metadata["cost_summary"] = {
        "total_monthly": round(report.total_monthly, 2),
        "by_category": {k: round(v, 2) for k, v in report.by_category.items()},
        "by_tier": {k: round(v, 2) for k, v in report.by_tier.items()},
        "currency": "USD",
    }

    return StackMapIR(
        metadata=metadata,
        nodes=annotated_nodes,
        edges=list(ir.edges),
        groups=list(ir.groups),
    )
