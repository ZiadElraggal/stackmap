"""Suspicious pattern detection: orphans, unused resources, public exposure, etc."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from stackmap.parsers.base import EdgeType, StackMapIR


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Finding:
    id: str
    pattern_id: str
    title: str
    description: str
    severity: Severity
    node_ids: list[str]
    recommendation: str
    category: str  # "orphan", "unused", "exposure", "cross-region", "cost", "monitoring"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pattern_id": self.pattern_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "node_ids": self.node_ids,
            "recommendation": self.recommendation,
            "remediation": self.recommendation,
            "category": self.category,
        }


def _finding_id(pattern_id: str, *args: str) -> str:
    """Generate a stable finding ID from pattern + resource identifiers."""
    raw = f"{pattern_id}:{'|'.join(args)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# Resource types that are expected to be leaf nodes (no edges is normal).
_EXPECTED_LEAF_TYPES = frozenset({
    "aws_iam_policy",
    "aws_iam_policy_attachment",
    "aws_iam_role_policy_attachment",
    "aws_cloudwatch_log_group",
    "aws_lambda_permission",
    "aws_sns_topic_subscription",
    "aws_route53_record",
    "aws_acm_certificate",
    "aws_kms_key",
    "aws_kms_alias",
    "aws_secretsmanager_secret_version",
    "aws_ssm_parameter",
})

_GLOBAL_SERVICE_TYPES = frozenset({
    "aws_cloudfront_distribution",
    "aws_route53_zone",
    "aws_route53_record",
    "aws_iam_role",
    "aws_iam_policy",
    "aws_iam_user",
    "aws_iam_group",
})


def analyze_patterns(ir: StackMapIR, *, include_security: bool = True) -> list[Finding]:
    """Run all pattern detectors on the IR and return findings."""
    findings: list[Finding] = []
    findings.extend(_detect_orphaned_resources(ir))
    findings.extend(_detect_unused_load_balancers(ir))
    findings.extend(_detect_cross_region_links(ir))
    findings.extend(_detect_public_exposure(ir))
    findings.extend(_detect_unencrypted_storage(ir))
    findings.extend(_detect_oversized_resources(ir))
    findings.extend(_detect_missing_monitoring(ir))
    if not include_security:
        return findings
    try:
        from stackmap.findings.security import detect_security_findings
        findings.extend(detect_security_findings(ir))
    except Exception:
        pass
    return findings


def _detect_orphaned_resources(ir: StackMapIR) -> list[Finding]:
    """Resources with 0 edges (not source or target of any edge)."""
    connected: set[str] = set()
    for edge in ir.edges:
        connected.add(edge.source)
        connected.add(edge.target)

    findings: list[Finding] = []
    for node in ir.nodes:
        if node.id in connected:
            continue
        if node.resource_type in _EXPECTED_LEAF_TYPES:
            continue
        findings.append(Finding(
            id=_finding_id("orphaned-resource", node.id),
            pattern_id="orphaned-resource",
            title=f"{node.resource_type} has no connections",
            description=(
                f"Resource '{node.name}' ({node.resource_type}) is not connected to any other "
                f"resource. It may be orphaned, unused, or missing relationship definitions."
            ),
            severity=Severity.WARNING,
            node_ids=[node.id],
            recommendation="Review whether this resource is still needed. If it's in use, check for missing relationship definitions.",
            category="orphan",
        ))
    return findings


def _detect_unused_load_balancers(ir: StackMapIR) -> list[Finding]:
    """ALB/NLB/CLB with no ROUTES_TO target edges."""
    lb_types = {
        "aws_lb", "aws_alb", "aws_elb",
        "aws_lb_target_group", "aws_alb_target_group",
    }
    # Build outgoing ROUTES_TO edges per source
    routes_to: dict[str, list[str]] = {}
    for edge in ir.edges:
        if edge.edge_type == EdgeType.ROUTES_TO:
            routes_to.setdefault(edge.source, []).append(edge.target)

    findings: list[Finding] = []
    for node in ir.nodes:
        if node.resource_type not in lb_types:
            continue
        targets = routes_to.get(node.id, [])
        if not targets:
            findings.append(Finding(
                id=_finding_id("unused-lb", node.id),
                pattern_id="unused-lb",
                title=f"Load balancer has no active targets",
                description=(
                    f"Load balancer '{node.name}' ({node.resource_type}) has no ROUTES_TO edges, "
                    f"meaning it may not be routing traffic to any backend."
                ),
                severity=Severity.WARNING,
                node_ids=[node.id],
                recommendation="Check if this load balancer has registered targets. Remove if no longer needed.",
                category="unused",
            ))
    return findings


def _detect_cross_region_links(ir: StackMapIR) -> list[Finding]:
    """Edges where source region differs from target region (excluding expected global patterns)."""
    node_map = {n.id: n for n in ir.nodes}

    findings: list[Finding] = []
    for edge in ir.edges:
        source_node = node_map.get(edge.source)
        target_node = node_map.get(edge.target)
        if not source_node or not target_node:
            continue

        source_region = source_node.metadata.get("region", "")
        target_region = target_node.metadata.get("region", "")

        if not source_region or not target_region:
            continue
        if source_region == target_region:
            continue

        # Expected cross-region patterns
        if source_node.resource_type in _GLOBAL_SERVICE_TYPES:
            continue
        if target_node.resource_type in _GLOBAL_SERVICE_TYPES:
            continue

        findings.append(Finding(
            id=_finding_id("cross-region", edge.id),
            pattern_id="cross-region",
            title=f"Unexpected cross-region link: {source_region} -> {target_region}",
            description=(
                f"Resource '{source_node.name}' in {source_region} is linked to "
                f"'{target_node.name}' in {target_region}. This may indicate "
                f"unintended cross-region dependencies."
            ),
            severity=Severity.INFO,
            node_ids=[source_node.id, target_node.id],
            recommendation="Verify this cross-region link is intentional. Consider co-locating resources if possible.",
            category="cross-region",
        ))
    return findings


def _detect_public_exposure(ir: StackMapIR) -> list[Finding]:
    """Resources that may be publicly accessible."""
    findings: list[Finding] = []

    for node in ir.nodes:
        props = node.properties

        # S3 public access
        if node.resource_type == "aws_s3_bucket":
            acl = props.get("acl", "")
            if acl in ("public-read", "public-read-write"):
                findings.append(Finding(
                    id=_finding_id("public-s3", node.id),
                    pattern_id="public-exposure",
                    title=f"S3 bucket has public ACL: {acl}",
                    description=f"Bucket '{node.name}' has ACL '{acl}' which allows public access.",
                    severity=Severity.CRITICAL,
                    node_ids=[node.id],
                    recommendation="Set ACL to 'private' and enable public access block.",
                    category="exposure",
                ))

        # Security group with 0.0.0.0/0 on sensitive ports
        if node.resource_type == "aws_security_group":
            ingress_rules = props.get("ingress", [])
            if isinstance(ingress_rules, list):
                for rule in ingress_rules:
                    if not isinstance(rule, dict):
                        continue
                    cidr_blocks = rule.get("cidr_blocks", [])
                    if not isinstance(cidr_blocks, list):
                        continue
                    if "0.0.0.0/0" in cidr_blocks:
                        from_port = rule.get("from_port", 0)
                        to_port = rule.get("to_port", 65535)
                        # Warn on non-standard web ports
                        if not (from_port == to_port and from_port in (80, 443)):
                            findings.append(Finding(
                                id=_finding_id("open-sg", node.id, str(from_port)),
                                pattern_id="public-exposure",
                                title=f"Security group allows 0.0.0.0/0 on port {from_port}-{to_port}",
                                description=(
                                    f"Security group '{node.name}' allows inbound traffic from "
                                    f"anywhere (0.0.0.0/0) on ports {from_port}-{to_port}."
                                ),
                                severity=Severity.CRITICAL,
                                node_ids=[node.id],
                                recommendation="Restrict the CIDR range to known IPs or use a VPN.",
                                category="exposure",
                            ))

        # RDS publicly accessible
        if node.resource_type in ("aws_db_instance", "aws_rds_cluster"):
            if props.get("publicly_accessible") is True:
                findings.append(Finding(
                    id=_finding_id("public-rds", node.id),
                    pattern_id="public-exposure",
                    title="RDS instance is publicly accessible",
                    description=f"Database '{node.name}' has publicly_accessible=true.",
                    severity=Severity.CRITICAL,
                    node_ids=[node.id],
                    recommendation="Set publicly_accessible to false unless required for development.",
                    category="exposure",
                ))

    return findings


def _detect_unencrypted_storage(ir: StackMapIR) -> list[Finding]:
    """Storage resources without encryption configuration."""
    findings: list[Finding] = []

    for node in ir.nodes:
        props = node.properties

        if node.resource_type == "aws_s3_bucket":
            sse = props.get("server_side_encryption_configuration")
            if not sse:
                findings.append(Finding(
                    id=_finding_id("unencrypted-s3", node.id),
                    pattern_id="unencrypted-storage",
                    title="S3 bucket has no encryption configured",
                    description=f"Bucket '{node.name}' has no server-side encryption configuration.",
                    severity=Severity.WARNING,
                    node_ids=[node.id],
                    recommendation="Enable server-side encryption (SSE-S3 or SSE-KMS).",
                    category="exposure",
                ))

        if node.resource_type in ("aws_db_instance", "aws_rds_cluster"):
            if props.get("storage_encrypted") is not True and props.get("StorageEncrypted") is not True:
                findings.append(Finding(
                    id=_finding_id("unencrypted-rds", node.id),
                    pattern_id="unencrypted-storage",
                    title="Database storage is not encrypted",
                    description=f"Database '{node.name}' does not have storage encryption enabled.",
                    severity=Severity.WARNING,
                    node_ids=[node.id],
                    recommendation="Enable storage encryption for the database.",
                    category="exposure",
                ))

        if node.resource_type == "aws_dynamodb_table":
            pitr = props.get("point_in_time_recovery")
            if not pitr:
                findings.append(Finding(
                    id=_finding_id("no-pitr-dynamo", node.id),
                    pattern_id="unencrypted-storage",
                    title="DynamoDB table has no point-in-time recovery",
                    description=f"Table '{node.name}' does not have PITR enabled.",
                    severity=Severity.INFO,
                    node_ids=[node.id],
                    recommendation="Enable point-in-time recovery for data protection.",
                    category="monitoring",
                ))

    return findings


def _detect_oversized_resources(ir: StackMapIR) -> list[Finding]:
    """Resources that may be over-provisioned."""
    _EXPENSIVE_RDS_CLASSES = frozenset({
        "db.r6g.16xlarge", "db.r6g.12xlarge", "db.r6g.8xlarge",
        "db.r5.24xlarge", "db.r5.16xlarge", "db.r5.12xlarge",
        "db.x2g.16xlarge", "db.x2g.12xlarge", "db.x2g.8xlarge",
    })

    findings: list[Finding] = []

    for node in ir.nodes:
        props = node.properties

        # Lambda with high memory but low timeout
        if node.resource_type == "aws_lambda_function":
            memory = props.get("memory_size", 0)
            timeout = props.get("timeout", 0)
            if isinstance(memory, (int, float)) and isinstance(timeout, (int, float)):
                if memory > 3008 and timeout < 10:
                    findings.append(Finding(
                        id=_finding_id("oversized-lambda", node.id),
                        pattern_id="oversized-resource",
                        title=f"Lambda has {memory}MB memory with only {timeout}s timeout",
                        description=(
                            f"Function '{node.name}' has {memory}MB memory but a {timeout}s timeout. "
                            f"High memory with low timeout suggests over-provisioning."
                        ),
                        severity=Severity.INFO,
                        node_ids=[node.id],
                        recommendation="Review memory allocation. Consider reducing memory if execution is fast.",
                        category="cost",
                    ))

        # Expensive RDS instances
        if node.resource_type in ("aws_db_instance", "aws_rds_cluster"):
            instance_class = props.get("instance_class", "")
            if instance_class in _EXPENSIVE_RDS_CLASSES:
                findings.append(Finding(
                    id=_finding_id("expensive-rds", node.id),
                    pattern_id="oversized-resource",
                    title=f"RDS using expensive instance class: {instance_class}",
                    description=f"Database '{node.name}' uses {instance_class} which is in the highest cost tier.",
                    severity=Severity.INFO,
                    node_ids=[node.id],
                    recommendation="Evaluate if a smaller instance class would meet performance requirements.",
                    category="cost",
                ))

    return findings


def _detect_missing_monitoring(ir: StackMapIR) -> list[Finding]:
    """Resources without corresponding monitoring/logging."""
    # Build set of resource types that have associated log groups
    log_group_targets: set[str] = set()
    for edge in ir.edges:
        if edge.edge_type in (EdgeType.WRITES_TO, EdgeType.TRIGGERS):
            log_group_targets.add(edge.source)

    # Check Lambda functions
    lambda_ids = {n.id for n in ir.nodes if n.resource_type == "aws_lambda_function"}
    log_group_names = {n.name for n in ir.nodes if n.resource_type == "aws_cloudwatch_log_group"}

    findings: list[Finding] = []
    for node in ir.nodes:
        if node.resource_type != "aws_lambda_function":
            continue

        # Check if there's a matching log group (by naming convention /aws/lambda/NAME)
        fn_name = node.properties.get("function_name", node.name)
        expected_log_group = f"/aws/lambda/{fn_name}"
        has_log_group = (
            expected_log_group in log_group_names
            or fn_name in log_group_names
            or node.id in log_group_targets
        )

        if not has_log_group:
            findings.append(Finding(
                id=_finding_id("no-monitoring", node.id),
                pattern_id="missing-monitoring",
                title=f"No monitoring detected for Lambda function",
                description=f"Function '{node.name}' has no associated CloudWatch log group.",
                severity=Severity.INFO,
                node_ids=[node.id],
                recommendation="Ensure CloudWatch logging is enabled for this function.",
                category="monitoring",
            ))

    return findings
