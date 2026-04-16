"""Security-oriented finding detectors."""

from __future__ import annotations

from collections.abc import Iterable

from stackmap.analysis.patterns import Finding, Severity, _finding_id
from stackmap.parsers.base import StackMapIR, StackMapNode


SENSITIVE_PORTS = {22, 3389, 3306, 5432, 6379, 9200}


def detect_security_findings(ir: StackMapIR) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(detect_public_s3(ir))
    findings.extend(detect_open_security_groups(ir))
    findings.extend(detect_wildcard_iam(ir))
    findings.extend(detect_unencrypted_storage(ir))
    findings.extend(detect_missing_logs(ir))
    return findings


def _as_list(value: object) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _policy_statements(value: object) -> list[dict]:
    if isinstance(value, str):
        return []
    if isinstance(value, dict):
        return [item for item in _as_list(value.get("Statement")) if isinstance(item, dict)]
    return []


def _contains_anywhere(cidr_value: object) -> bool:
    cidrs = _as_list(cidr_value)
    return "0.0.0.0/0" in cidrs or "::/0" in cidrs


def detect_public_s3(ir: StackMapIR) -> list[Finding]:
    findings: list[Finding] = []
    for node in ir.nodes:
        if node.resource_type not in {"aws_s3_bucket", "AWS::S3::Bucket"}:
            continue
        props = node.properties
        acl = props.get("acl") or props.get("AccessControl")
        policy = props.get("policy") or props.get("PolicyDocument")
        public_policy = any(
            statement.get("Effect") == "Allow"
            and statement.get("Principal") in {"*", {"AWS": "*"}}
            for statement in _policy_statements(policy)
        )
        if acl in {"public-read", "public-read-write", "PublicRead", "PublicReadWrite"} or public_policy:
            findings.append(Finding(
                id=_finding_id("s3.public_bucket", node.id),
                pattern_id="s3.public_bucket",
                title="Public S3 bucket",
                description=f"Bucket '{node.name}' allows public access through ACL or policy.",
                severity=Severity.CRITICAL,
                node_ids=[node.id],
                recommendation="Enable S3 Block Public Access and remove public ACL/policy statements.",
                category="security",
            ))
    return findings


def _rule_ports(rule: dict) -> Iterable[int]:
    from_port = rule.get("from_port", rule.get("FromPort", 0))
    to_port = rule.get("to_port", rule.get("ToPort", from_port))
    try:
        start = int(from_port)
        end = int(to_port)
    except (TypeError, ValueError):
        yield 0
        return
    for port in SENSITIVE_PORTS:
        if start <= port <= end:
            yield port


def detect_open_security_groups(ir: StackMapIR) -> list[Finding]:
    findings: list[Finding] = []
    for node in ir.nodes:
        if node.resource_type not in {"aws_security_group", "AWS::EC2::SecurityGroup"}:
            continue
        for rule in _as_list(node.properties.get("ingress") or node.properties.get("SecurityGroupIngress")):
            if not isinstance(rule, dict):
                continue
            cidrs = rule.get("cidr_blocks", rule.get("CidrIp"))
            ipv6 = rule.get("ipv6_cidr_blocks", rule.get("CidrIpv6"))
            if not (_contains_anywhere(cidrs) or _contains_anywhere(ipv6)):
                continue
            for port in _rule_ports(rule):
                findings.append(Finding(
                    id=_finding_id("sg.open_sensitive_port", node.id, str(port)),
                    pattern_id="sg.open_sensitive_port",
                    title=f"Security group exposes port {port}",
                    description=f"Security group '{node.name}' allows internet ingress on sensitive port {port}.",
                    severity=Severity.CRITICAL,
                    node_ids=[node.id],
                    recommendation="Restrict ingress to trusted CIDRs, VPN ranges, or private security groups.",
                    category="security",
                ))
    return findings


def _node_policy_documents(node: StackMapNode) -> list[dict]:
    candidates = [
        node.properties.get("policy"),
        node.properties.get("policy_document"),
        node.properties.get("PolicyDocument"),
        node.properties.get("assume_role_policy"),
    ]
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def _matches_star(value: object) -> bool:
    values = _as_list(value)
    return "*" in values or "*:*" in values


def detect_wildcard_iam(ir: StackMapIR) -> list[Finding]:
    findings: list[Finding] = []
    for node in ir.nodes:
        if "iam" not in node.resource_type.lower():
            continue
        for document in _node_policy_documents(node):
            for statement in _policy_statements(document):
                if statement.get("Effect", "Allow") != "Allow":
                    continue
                if _matches_star(statement.get("Action")) and _matches_star(statement.get("Resource")):
                    findings.append(Finding(
                        id=_finding_id("iam.wildcard_admin", node.id),
                        pattern_id="iam.wildcard_admin",
                        title="IAM policy allows * on *",
                        description=f"IAM resource '{node.name}' grants wildcard actions on wildcard resources.",
                        severity=Severity.CRITICAL,
                        node_ids=[node.id],
                        recommendation="Replace wildcard permissions with least-privilege service actions and resources.",
                        category="security",
                    ))
                    break
    return findings


def detect_unencrypted_storage(ir: StackMapIR) -> list[Finding]:
    findings: list[Finding] = []
    for node in ir.nodes:
        props = node.properties
        if node.resource_type in {"aws_ebs_volume", "AWS::EC2::Volume"} and props.get("encrypted") is not True and props.get("Encrypted") is not True:
            findings.append(Finding(
                id=_finding_id("storage.unencrypted_ebs", node.id),
                pattern_id="storage.unencrypted_ebs",
                title="EBS volume is not encrypted",
                description=f"Volume '{node.name}' does not declare encryption.",
                severity=Severity.WARNING,
                node_ids=[node.id],
                recommendation="Enable EBS encryption or use an encrypted default volume policy.",
                category="security",
            ))
    return findings


def detect_missing_logs(ir: StackMapIR) -> list[Finding]:
    findings: list[Finding] = []
    for node in ir.nodes:
        props = node.properties
        if node.resource_type in {"aws_cloudfront_distribution", "AWS::CloudFront::Distribution"} and not props.get("logging_config") and not props.get("Logging"):
            findings.append(Finding(
                id=_finding_id("logs.cloudfront_missing", node.id),
                pattern_id="logs.cloudfront_missing",
                title="CloudFront access logging is disabled",
                description=f"Distribution '{node.name}' does not expose access logging configuration.",
                severity=Severity.INFO,
                node_ids=[node.id],
                recommendation="Enable access logs to S3 or centralize request logs for investigation.",
                category="security",
            ))
    return findings
