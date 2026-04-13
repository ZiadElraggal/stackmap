"""AWS billing integration: fetch real usage data from Cost Explorer and CloudWatch metrics.

This module provides optional billing data integration that requires additional
IAM permissions beyond the standard StackMap read-only policy:
  - ce:GetCostAndUsage (Cost Explorer)
  - cloudwatch:GetMetricStatistics (CloudWatch metrics for invocation counts)

When enabled, it replaces heuristic-based estimates with actual billing data,
giving users accurate current costs and enabling current-vs-forecasted comparisons.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

# Resource type -> (service namespace, metric for usage)
_USAGE_METRIC_MAP: dict[str, dict] = {
    "aws_lambda_function": {
        "namespace": "AWS/Lambda",
        "metric": "Invocations",
        "stat": "Sum",
        "dimension_key": "FunctionName",
        "property_key": "function_name",
    },
    "aws_dynamodb_table": {
        "namespace": "AWS/DynamoDB",
        "metric": "ConsumedReadCapacityUnits",
        "stat": "Sum",
        "dimension_key": "TableName",
        "property_key": "id",
    },
    "aws_s3_bucket": {
        "namespace": "AWS/S3",
        "metric": "BucketSizeBytes",
        "stat": "Average",
        "dimension_key": "BucketName",
        "property_key": "id",
    },
    "aws_api_gateway_rest_api": {
        "namespace": "AWS/ApiGateway",
        "metric": "Count",
        "stat": "Sum",
        "dimension_key": "ApiName",
        "property_key": "id",
    },
    "aws_cloudfront_distribution": {
        "namespace": "AWS/CloudFront",
        "metric": "BytesDownloaded",
        "stat": "Sum",
        "dimension_key": "DistributionId",
        "property_key": "id",
        "region": "us-east-1",
        "extra_dimensions": {"Region": "Global"},
    },
}


@dataclass
class BillingEntry:
    """A single billing line item for a resource or service."""
    resource_id: str
    service: str
    monthly_cost: float
    currency: str = "USD"
    usage_quantity: float | None = None
    usage_unit: str | None = None
    period_start: str = ""
    period_end: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "resource_id": self.resource_id,
            "service": self.service,
            "monthly_cost": round(self.monthly_cost, 2),
            "currency": self.currency,
        }
        if self.usage_quantity is not None:
            d["usage_quantity"] = self.usage_quantity
            d["usage_unit"] = self.usage_unit
        if self.period_start:
            d["period_start"] = self.period_start
            d["period_end"] = self.period_end
        return d


@dataclass
class BillingReport:
    """Aggregated billing data for an AWS account."""
    total_monthly: float = 0.0
    by_service: dict[str, float] = field(default_factory=dict)
    by_resource: dict[str, BillingEntry] = field(default_factory=dict)
    usage_metrics: dict[str, dict] = field(default_factory=dict)
    period_start: str = ""
    period_end: str = ""
    currency: str = "USD"

    def to_dict(self) -> dict:
        return {
            "total_monthly": round(self.total_monthly, 2),
            "by_service": {k: round(v, 2) for k, v in self.by_service.items()},
            "by_resource": {k: v.to_dict() for k, v in self.by_resource.items()},
            "usage_metrics": self.usage_metrics,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "currency": self.currency,
        }


def fetch_billing_data(session: "boto3.Session", *, days: int = 30) -> BillingReport:
    """Fetch billing data from AWS Cost Explorer for the last N days.

    Requires IAM permission: ce:GetCostAndUsage
    """
    import boto3

    ce = session.client("ce")
    end = datetime.now(tz=UTC).date()
    start = end - timedelta(days=days)

    report = BillingReport(
        period_start=start.isoformat(),
        period_end=end.isoformat(),
    )

    try:
        # Get cost by service
        result = ce.get_cost_and_usage(
            TimePeriod={
                "Start": start.isoformat(),
                "End": end.isoformat(),
            },
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        for time_period in result.get("ResultsByTime", []):
            for group in time_period.get("Groups", []):
                service_name = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                report.by_service[service_name] = (
                    report.by_service.get(service_name, 0) + amount
                )

        # Normalize to monthly (if period < 30 days, scale up)
        actual_days = (end - start).days or 1
        scale = 30.0 / actual_days

        for service in report.by_service:
            report.by_service[service] *= scale

        report.total_monthly = sum(report.by_service.values())

    except Exception as exc:
        logger.warning("Cost Explorer query failed: %s", exc)

    return report


def fetch_usage_metrics(
    session: "boto3.Session",
    resource_type: str,
    resource_name: str,
    region: str = "us-east-1",
    *,
    days: int = 30,
) -> dict:
    """Fetch CloudWatch usage metrics for a specific resource.

    Returns a dict with metric values that can be used as cost overrides:
      - Lambda: {"invocations_per_month": N, "avg_duration_ms": N}
      - DynamoDB: {"read_units": N, "write_units": N}
      - S3: {"storage_gb": N}
      - API Gateway: {"requests_per_month": N}

    Requires IAM permission: cloudwatch:GetMetricStatistics
    """
    metric_config = _USAGE_METRIC_MAP.get(resource_type)
    if not metric_config:
        return {}

    metric_region = metric_config.get("region", region)
    cw = session.client("cloudwatch", region_name=metric_region)
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days)

    result: dict = {}

    try:
        response = cw.get_metric_statistics(
            Namespace=metric_config["namespace"],
            MetricName=metric_config["metric"],
            Dimensions=[
                {
                    "Name": metric_config["dimension_key"],
                    "Value": resource_name,
                },
                *[
                    {"Name": key, "Value": value}
                    for key, value in metric_config.get("extra_dimensions", {}).items()
                ],
            ],
            StartTime=start,
            EndTime=end,
            Period=days * 86400,  # entire period as one datapoint
            Statistics=[metric_config["stat"]],
        )

        datapoints = response.get("Datapoints", [])
        if datapoints:
            value = datapoints[0].get(metric_config["stat"], 0)
            actual_days = days or 1
            monthly_scale = 30.0 / actual_days

            if resource_type == "aws_lambda_function":
                result["invocations_per_month"] = int(value * monthly_scale)
                # Also try to get duration
                dur_response = cw.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Duration",
                    Dimensions=[
                        {"Name": "FunctionName", "Value": resource_name}
                    ],
                    StartTime=start,
                    EndTime=end,
                    Period=days * 86400,
                    Statistics=["Average"],
                )
                dur_points = dur_response.get("Datapoints", [])
                if dur_points:
                    result["avg_duration_ms"] = round(
                        dur_points[0].get("Average", 200), 1
                    )

            elif resource_type == "aws_s3_bucket":
                result["storage_gb"] = round(value / (1024**3), 2)

            elif resource_type == "aws_api_gateway_rest_api":
                result["requests_per_month"] = int(value * monthly_scale)

            elif resource_type == "aws_dynamodb_table":
                result["read_capacity_units"] = int(value * monthly_scale)

            elif resource_type == "aws_cloudfront_distribution":
                result["data_transfer_gb"] = round((value * monthly_scale) / (1024**3), 2)

    except Exception as exc:
        logger.warning(
            "CloudWatch metrics query failed for %s/%s: %s",
            resource_type,
            resource_name,
            exc,
        )

    return result


def fetch_all_usage_metrics(
    session: "boto3.Session",
    ir: "StackMapIR",
) -> dict[str, dict]:
    """Fetch CloudWatch usage metrics for all supported nodes in an IR.

    Returns a dict mapping node_id -> usage override dict suitable for
    passing to estimate_costs(ir, overrides=...).
    """
    from stackmap.parsers.base import StackMapIR  # noqa: F811

    overrides: dict[str, dict] = {}

    for node in ir.nodes:
        metric_config = _USAGE_METRIC_MAP.get(node.resource_type)
        if not metric_config:
            continue

        prop_key = metric_config["property_key"]
        resource_name = node.properties.get(prop_key) or node.name
        region = node.metadata.get("region", "us-east-1")

        usage = fetch_usage_metrics(
            session,
            node.resource_type,
            resource_name,
            region=region,
        )

        if usage:
            overrides[node.id] = usage

    return overrides
