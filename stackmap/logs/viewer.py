"""CloudWatch log viewer: fetch and search live logs for infrastructure resources.

This module provides optional log viewing capabilities that require additional
IAM permissions beyond the standard StackMap read-only policy:
  - logs:FilterLogEvents
  - logs:DescribeLogGroups
  - logs:GetLogEvents

Supported resource types and their log group patterns:
  - Lambda functions: /aws/lambda/{function_name}
  - API Gateway: /aws/apigateway/{api_id} or API-Gateway-Execution-Logs_{api_id}
  - ECS services: /ecs/{cluster}/{service}
  - Step Functions: /aws/vendedlogs/states/{state_machine_name}
  - RDS: /aws/rds/instance/{db_identifier}/...
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

# Resource type -> list of log group patterns to try
_LOG_GROUP_PATTERNS: dict[str, list[str]] = {
    "aws_lambda_function": ["/aws/lambda/{name}"],
    "aws_api_gateway_rest_api": [
        "API-Gateway-Execution-Logs_{id}/{stage}",
        "/aws/apigateway/{id}",
    ],
    "aws_ecs_service": ["/ecs/{cluster}/{name}"],
    "aws_sfn_state_machine": ["/aws/vendedlogs/states/{name}"],
    "aws_db_instance": [
        "/aws/rds/instance/{id}/error",
        "/aws/rds/instance/{id}/general",
        "/aws/rds/instance/{id}/slowquery",
    ],
    "aws_rds_cluster": [
        "/aws/rds/cluster/{id}/error",
        "/aws/rds/cluster/{id}/audit",
    ],
}


@dataclass
class LogEvent:
    """A single log event."""
    timestamp: int  # epoch ms
    message: str
    log_group: str
    log_stream: str = ""
    ingestion_time: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "message": self.message,
            "log_group": self.log_group,
            "log_stream": self.log_stream,
        }


@dataclass
class LogQueryResult:
    """Result of a log query."""
    events: list[LogEvent] = field(default_factory=list)
    log_groups: list[str] = field(default_factory=list)
    truncated: bool = False
    error: str | None = None
    scanned_bytes: int = 0

    def to_dict(self) -> dict:
        return {
            "events": [e.to_dict() for e in self.events],
            "log_groups": self.log_groups,
            "truncated": self.truncated,
            "error": self.error,
            "count": len(self.events),
        }


def _resolve_log_groups(
    resource_type: str,
    node_properties: dict,
    node_name: str,
) -> list[str]:
    """Resolve potential CloudWatch log group names for a resource."""
    patterns = _LOG_GROUP_PATTERNS.get(resource_type, [])
    if not patterns:
        return []

    groups: list[str] = []
    name = node_properties.get("function_name") or node_name
    resource_id = node_properties.get("id") or node_name
    cluster = node_properties.get("cluster", "default")

    for pattern in patterns:
        group = pattern.format(
            name=name,
            id=resource_id,
            cluster=cluster,
            stage="*",
        )
        groups.append(group)

    return groups


def _find_existing_log_groups(
    logs_client: "botocore.client.CloudWatchLogs",
    candidates: list[str],
) -> list[str]:
    """Check which candidate log group names actually exist."""
    found: list[str] = []
    for candidate in candidates:
        prefix = candidate.rstrip("*")
        try:
            response = logs_client.describe_log_groups(
                logGroupNamePrefix=prefix,
                limit=5,
            )
            for group in response.get("logGroups", []):
                group_name = group["logGroupName"]
                if "*" in candidate:
                    found.append(group_name)
                elif group_name == candidate:
                    found.append(group_name)
        except Exception as exc:
            logger.debug("Could not check log group %s: %s", candidate, exc)
    return found


def fetch_resource_logs(
    session: "boto3.Session",
    resource_type: str,
    node_properties: dict,
    node_name: str,
    region: str = "us-east-1",
    *,
    minutes: int = 60,
    limit: int = 200,
    filter_pattern: str = "",
) -> LogQueryResult:
    """Fetch recent logs for a specific resource.

    Args:
        session: boto3 session with appropriate permissions.
        resource_type: StackMap resource type (e.g., "aws_lambda_function").
        node_properties: Node properties dict.
        node_name: Display name of the resource.
        region: AWS region.
        minutes: How far back to look (default 60 min).
        limit: Max events to return (default 200).
        filter_pattern: CloudWatch filter pattern for server-side filtering.

    Returns:
        LogQueryResult with matching events.
    """
    result = LogQueryResult()

    candidates = _resolve_log_groups(resource_type, node_properties, node_name)
    if not candidates:
        result.error = f"No log group pattern known for {resource_type}"
        return result

    try:
        logs_client = session.client("logs", region_name=region)
    except Exception as exc:
        result.error = f"Could not create CloudWatch Logs client: {exc}"
        return result

    existing = _find_existing_log_groups(logs_client, candidates)
    if not existing:
        result.error = f"No log groups found matching: {', '.join(candidates)}"
        return result

    result.log_groups = existing
    end_time = int(datetime.now(tz=UTC).timestamp() * 1000)
    start_time = end_time - (minutes * 60 * 1000)

    for log_group in existing:
        try:
            kwargs: dict = {
                "logGroupName": log_group,
                "startTime": start_time,
                "endTime": end_time,
                "limit": limit - len(result.events),
                "interleaved": True,
            }
            if filter_pattern:
                kwargs["filterPattern"] = filter_pattern

            response = logs_client.filter_log_events(**kwargs)

            for event in response.get("events", []):
                result.events.append(LogEvent(
                    timestamp=event.get("timestamp", 0),
                    message=event.get("message", "").rstrip("\n"),
                    log_group=log_group,
                    log_stream=event.get("logStreamName", ""),
                    ingestion_time=event.get("ingestionTime", 0),
                ))

            if response.get("nextToken"):
                result.truncated = True

        except Exception as exc:
            logger.warning("Failed to fetch logs from %s: %s", log_group, exc)
            if not result.error:
                result.error = f"Partial failure: {exc}"

        if len(result.events) >= limit:
            result.truncated = True
            break

    # Sort by timestamp descending (newest first)
    result.events.sort(key=lambda e: e.timestamp, reverse=True)
    return result


def search_logs(
    events: list[LogEvent],
    query: str,
) -> list[LogEvent]:
    """Client-side search/filter on already-fetched log events.

    Supports simple text search and basic regex patterns.
    """
    if not query.strip():
        return events

    # Try as regex first, fall back to case-insensitive substring
    try:
        pattern = re.compile(query, re.IGNORECASE)
        return [e for e in events if pattern.search(e.message)]
    except re.error:
        query_lower = query.lower()
        return [e for e in events if query_lower in e.message.lower()]


def list_available_log_groups(
    session: "boto3.Session",
    ir: "StackMapIR",
    region: str = "us-east-1",
) -> dict[str, list[str]]:
    """For all nodes in IR, discover which have CloudWatch log groups.

    Returns a dict mapping node_id -> list of log group names.
    """
    logs_client = session.client("logs", region_name=region)
    node_logs: dict[str, list[str]] = {}

    for node in ir.nodes:
        candidates = _resolve_log_groups(
            node.resource_type, node.properties, node.name
        )
        if not candidates:
            continue

        existing = _find_existing_log_groups(logs_client, candidates)
        if existing:
            node_logs[node.id] = existing

    return node_logs
