"""Terraform state file parser."""

import json
from pathlib import Path

from stackmap.parsers.base import (
    BaseParser,
    EdgeType,
    ResourceCategory,
    StackMapEdge,
    StackMapGroup,
    StackMapIR,
    StackMapNode,
)

# Maps Terraform resource types to StackMap categories
RESOURCE_CATEGORY_MAP: dict[str, ResourceCategory] = {
    # Compute
    "aws_lambda_function": ResourceCategory.COMPUTE,
    "aws_instance": ResourceCategory.COMPUTE,
    "aws_launch_template": ResourceCategory.COMPUTE,
    "aws_autoscaling_group": ResourceCategory.COMPUTE,
    # Containers
    "aws_ecs_cluster": ResourceCategory.CONTAINER,
    "aws_ecs_service": ResourceCategory.CONTAINER,
    "aws_ecs_task_definition": ResourceCategory.CONTAINER,
    "aws_ecr_repository": ResourceCategory.CONTAINER,
    # Serverless / Integration
    "aws_sfn_state_machine": ResourceCategory.INTEGRATION,
    "aws_api_gateway_rest_api": ResourceCategory.INTEGRATION,
    "aws_api_gateway_deployment": ResourceCategory.INTEGRATION,
    "aws_api_gateway_stage": ResourceCategory.INTEGRATION,
    "aws_apigatewayv2_api": ResourceCategory.INTEGRATION,
    # Storage
    "aws_s3_bucket": ResourceCategory.STORAGE,
    "aws_s3_bucket_policy": ResourceCategory.STORAGE,
    "aws_s3_bucket_versioning": ResourceCategory.STORAGE,
    "aws_s3_bucket_server_side_encryption_configuration": ResourceCategory.STORAGE,
    "aws_s3_bucket_public_access_block": ResourceCategory.STORAGE,
    # Database
    "aws_dynamodb_table": ResourceCategory.DATABASE,
    "aws_rds_cluster": ResourceCategory.DATABASE,
    "aws_db_instance": ResourceCategory.DATABASE,
    "aws_db_subnet_group": ResourceCategory.DATABASE,
    "aws_elasticache_cluster": ResourceCategory.DATABASE,
    "aws_elasticache_subnet_group": ResourceCategory.DATABASE,
    # Network
    "aws_vpc": ResourceCategory.NETWORK,
    "aws_subnet": ResourceCategory.NETWORK,
    "aws_internet_gateway": ResourceCategory.NETWORK,
    "aws_nat_gateway": ResourceCategory.NETWORK,
    "aws_eip": ResourceCategory.NETWORK,
    "aws_route_table": ResourceCategory.NETWORK,
    "aws_route_table_association": ResourceCategory.NETWORK,
    "aws_security_group": ResourceCategory.NETWORK,
    "aws_lb": ResourceCategory.NETWORK,
    "aws_lb_target_group": ResourceCategory.NETWORK,
    "aws_lb_listener": ResourceCategory.NETWORK,
    "aws_lb_listener_rule": ResourceCategory.NETWORK,
    "aws_alb": ResourceCategory.NETWORK,
    "aws_alb_target_group": ResourceCategory.NETWORK,
    "aws_alb_listener": ResourceCategory.NETWORK,
    "aws_vpc_peering_connection": ResourceCategory.NETWORK,
    # Security
    "aws_iam_role": ResourceCategory.SECURITY,
    "aws_iam_role_policy": ResourceCategory.SECURITY,
    "aws_iam_role_policy_attachment": ResourceCategory.SECURITY,
    "aws_iam_policy": ResourceCategory.SECURITY,
    "aws_lambda_permission": ResourceCategory.SECURITY,
    # Monitoring
    "aws_cloudwatch_log_group": ResourceCategory.MONITORING,
    "aws_cloudwatch_metric_alarm": ResourceCategory.MONITORING,
    "aws_flow_log": ResourceCategory.MONITORING,
    # CDN
    "aws_cloudfront_distribution": ResourceCategory.CDN,
    "aws_cloudfront_origin_access_control": ResourceCategory.CDN,
    # DNS
    "aws_route53_zone": ResourceCategory.DNS,
    "aws_route53_record": ResourceCategory.DNS,
    # Queue
    "aws_sqs_queue": ResourceCategory.QUEUE,
    "aws_sns_topic": ResourceCategory.QUEUE,
    "aws_sns_topic_subscription": ResourceCategory.QUEUE,
    # EventBridge
    "aws_cloudwatch_event_rule": ResourceCategory.INTEGRATION,
    "aws_cloudwatch_event_target": ResourceCategory.INTEGRATION,
    "aws_scheduler_schedule": ResourceCategory.INTEGRATION,
    # Kinesis
    "aws_kinesis_stream": ResourceCategory.QUEUE,
    "aws_kinesis_firehose_delivery_stream": ResourceCategory.QUEUE,
    # Secrets & Config
    "aws_secretsmanager_secret": ResourceCategory.SECURITY,
    "aws_secretsmanager_secret_version": ResourceCategory.SECURITY,
    "aws_ssm_parameter": ResourceCategory.SECURITY,
    # Cognito
    "aws_cognito_user_pool": ResourceCategory.SECURITY,
    "aws_cognito_user_pool_client": ResourceCategory.SECURITY,
    "aws_cognito_identity_pool": ResourceCategory.SECURITY,
    # WAF
    "aws_wafv2_web_acl": ResourceCategory.SECURITY,
    "aws_wafv2_web_acl_association": ResourceCategory.SECURITY,
    # ElastiCache (replication)
    "aws_elasticache_replication_group": ResourceCategory.DATABASE,
    # ACM
    "aws_acm_certificate": ResourceCategory.SECURITY,
    "aws_acm_certificate_validation": ResourceCategory.SECURITY,
    # Step Functions
    "aws_sfn_state_machine": ResourceCategory.INTEGRATION,
    # AppSync
    "aws_appsync_graphql_api": ResourceCategory.INTEGRATION,
    "aws_appsync_datasource": ResourceCategory.INTEGRATION,
    "aws_appsync_resolver": ResourceCategory.INTEGRATION,
    # ECR
    "aws_ecr_repository": ResourceCategory.CONTAINER,
    "aws_ecr_lifecycle_policy": ResourceCategory.CONTAINER,
    # S3 extras
    "aws_s3_bucket_website_configuration": ResourceCategory.STORAGE,
    "aws_s3_bucket_cors_configuration": ResourceCategory.STORAGE,
    "aws_s3_bucket_lifecycle_configuration": ResourceCategory.STORAGE,
    "aws_s3_bucket_notification": ResourceCategory.STORAGE,
    # SES
    "aws_ses_domain_identity": ResourceCategory.INTEGRATION,
    "aws_ses_email_identity": ResourceCategory.INTEGRATION,
}

# Tier assignments for layout hints
TIER_MAP: dict[ResourceCategory, str] = {
    ResourceCategory.CDN: "frontend",
    ResourceCategory.DNS: "frontend",
    ResourceCategory.INTEGRATION: "api",
    ResourceCategory.NETWORK: "api",
    ResourceCategory.COMPUTE: "backend",
    ResourceCategory.CONTAINER: "backend",
    ResourceCategory.SERVERLESS: "backend",
    ResourceCategory.SECURITY: "backend",
    ResourceCategory.MONITORING: "backend",
    ResourceCategory.QUEUE: "backend",
    ResourceCategory.STORAGE: "data",
    ResourceCategory.DATABASE: "data",
    ResourceCategory.OTHER: "backend",
}

# Weight by resource type (higher = more prominent in layout)
WEIGHT_MAP: dict[str, int] = {
    "aws_lambda_function": 5,
    "aws_ecs_service": 5,
    "aws_ecs_cluster": 4,
    "aws_sfn_state_machine": 5,
    "aws_api_gateway_rest_api": 5,
    "aws_dynamodb_table": 5,
    "aws_db_instance": 5,
    "aws_rds_cluster": 5,
    "aws_s3_bucket": 4,
    "aws_elasticache_cluster": 4,
    "aws_lb": 5,
    "aws_cloudfront_distribution": 5,
    "aws_vpc": 3,
    "aws_subnet": 2,
    "aws_sqs_queue": 4,
    "aws_sns_topic": 4,
    "aws_iam_role": 2,
    "aws_security_group": 2,
    "aws_cloudwatch_log_group": 1,
    "aws_iam_role_policy_attachment": 1,
    "aws_iam_role_policy": 1,
    "aws_lambda_permission": 1,
    "aws_route_table": 1,
    "aws_route_table_association": 1,
    "aws_apigatewayv2_api": 5,
    "aws_kinesis_stream": 4,
    "aws_kinesis_firehose_delivery_stream": 4,
    "aws_cloudwatch_event_rule": 3,
    "aws_secretsmanager_secret": 3,
    "aws_cognito_user_pool": 4,
    "aws_wafv2_web_acl": 3,
    "aws_elasticache_replication_group": 5,
    "aws_appsync_graphql_api": 5,
    "aws_ecr_repository": 3,
    "aws_route53_zone": 3,
    "aws_route53_record": 2,
    "aws_acm_certificate": 2,
}

# Attribute names to try for human-readable name, in priority order
NAME_ATTRIBUTES = [
    "function_name",
    "name",
    "bucket",
    "domain_name",
    "cluster_identifier",
    "cluster_id",
    "db_name",
    "identifier",
    "family",
    "id",
]


def _extract_provider(provider_str: str) -> str:
    """Extract provider name from Terraform provider string."""
    # e.g. 'provider["registry.terraform.io/hashicorp/aws"]' -> 'aws'
    if "/" in provider_str:
        return provider_str.rstrip('"]').rsplit("/", 1)[-1]
    return provider_str.strip('"[]')


def _resolve_name(resource_type: str, resource_name: str, attrs: dict) -> str:
    """Resolve a human-readable name from resource attributes."""
    for attr_name in NAME_ATTRIBUTES:
        val = attrs.get(attr_name)
        if val and isinstance(val, str) and val != "":
            return str(val)
    return resource_name


def _build_node_id(module: str | None, resource_type: str, name: str, index: str | None) -> str:
    """Build a unique node ID from Terraform resource address components."""
    parts = []
    if module:
        parts.append(module)
    parts.append(f"{resource_type}.{name}")
    if index is not None:
        parts.append(f"[{index}]")
    return ".".join(parts) if module else "".join(parts)


def _resolve_attribute_path(attrs: dict, path: str) -> list[str]:
    """Resolve an attribute path to a list of string values.

    Supports dotted paths (e.g. "vpc_config.0.subnet_ids") and returns
    all string values found. Handles lists and nested dicts.
    """
    parts = path.split(".")
    current: list = [attrs]

    for part in parts:
        next_vals: list = []
        for val in current:
            if isinstance(val, dict):
                child = val.get(part)
                if child is not None:
                    next_vals.append(child)
            elif isinstance(val, list):
                if part.isdigit():
                    idx = int(part)
                    if 0 <= idx < len(val):
                        next_vals.append(val[idx])
                elif part == "*":
                    next_vals.extend(val)
                else:
                    # Try to access each dict in the list
                    for item in val:
                        if isinstance(item, dict):
                            child = item.get(part)
                            if child is not None:
                                next_vals.append(child)
        current = next_vals

    # Flatten to strings
    results: list[str] = []
    for val in current:
        if isinstance(val, str) and val:
            results.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item:
                    results.append(item)
    return results


# Relationship rules: (source_type, attribute_path, edge_type, label, target_type_filter)
# target_type_filter is optional — if set, only match targets of that resource type
RELATIONSHIP_RULES: list[tuple[str, str, EdgeType, str, str | None]] = [
    # Lambda → IAM Role
    ("aws_lambda_function", "role", EdgeType.AUTHENTICATES, "assumes role", "aws_iam_role"),
    # Lambda permission: source_arn → function_name (reverse: API GW triggers Lambda)
    # Handled specially below
    # ECS Service → Cluster
    ("aws_ecs_service", "cluster", EdgeType.REFERENCES, "runs in", "aws_ecs_cluster"),
    # ECS Service → Task Definition
    ("aws_ecs_service", "task_definition", EdgeType.REFERENCES, "uses", None),
    # ECS Service → Subnets
    ("aws_ecs_service", "network_configuration.0.subnets", EdgeType.REFERENCES, "in subnet", None),
    # ECS Service → Security Groups
    (
        "aws_ecs_service",
        "network_configuration.0.security_groups",
        EdgeType.REFERENCES,
        "secured by",
        None,
    ),
    # ALB → Subnets
    ("aws_lb", "subnets", EdgeType.REFERENCES, "in subnet", None),
    # ALB → Security Groups
    ("aws_lb", "security_groups", EdgeType.REFERENCES, "secured by", None),
    # ALB Listener → ALB
    ("aws_lb_listener", "load_balancer_arn", EdgeType.ROUTES_TO, "listens on", "aws_lb"),
    # ALB Listener → Target Group
    (
        "aws_lb_listener",
        "default_action.*.target_group_arn",
        EdgeType.ROUTES_TO,
        "forwards to",
        "aws_lb_target_group",
    ),
    # ALB Target Group (connected via listener rules)
    (
        "aws_lb_listener_rule",
        "listener_arn",
        EdgeType.ROUTES_TO,
        "rule on",
        "aws_lb_listener",
    ),
    # ALB Listener Rule → Target Group
    (
        "aws_lb_listener_rule",
        "action.*.target_group_arn",
        EdgeType.ROUTES_TO,
        "forwards to",
        "aws_lb_target_group",
    ),
    # ECS Service → Target Group
    (
        "aws_ecs_service",
        "load_balancer.*.target_group_arn",
        EdgeType.ROUTES_TO,
        "serves via",
        "aws_lb_target_group",
    ),
    # RDS → Subnet Group
    (
        "aws_db_instance",
        "db_subnet_group_name",
        EdgeType.REFERENCES,
        "in subnet group",
        None,
    ),
    # RDS → Security Groups
    (
        "aws_db_instance",
        "vpc_security_group_ids",
        EdgeType.REFERENCES,
        "secured by",
        None,
    ),
    # ElastiCache → Subnet Group
    (
        "aws_elasticache_cluster",
        "subnet_group_name",
        EdgeType.REFERENCES,
        "in subnet group",
        None,
    ),
    # ElastiCache → Security Groups
    (
        "aws_elasticache_cluster",
        "security_group_ids",
        EdgeType.REFERENCES,
        "secured by",
        None,
    ),
    # Lambda → VPC Subnets
    (
        "aws_lambda_function",
        "vpc_config.0.subnet_ids",
        EdgeType.REFERENCES,
        "in subnet",
        None,
    ),
    # Lambda → VPC Security Groups
    (
        "aws_lambda_function",
        "vpc_config.0.security_group_ids",
        EdgeType.REFERENCES,
        "secured by",
        None,
    ),
    # SNS Subscription → Topic
    (
        "aws_sns_topic_subscription",
        "topic_arn",
        EdgeType.REFERENCES,
        "subscribes to",
        "aws_sns_topic",
    ),
    # SNS Subscription → Lambda (endpoint)
    (
        "aws_sns_topic_subscription",
        "endpoint",
        EdgeType.TRIGGERS,
        "triggers",
        "aws_lambda_function",
    ),
    # Route53 Record → Route53 Zone
    (
        "aws_route53_record",
        "zone_id",
        EdgeType.REFERENCES,
        "in zone",
        "aws_route53_zone",
    ),
    # Subnet → VPC
    ("aws_subnet", "vpc_id", EdgeType.CONTAINS, "in vpc", "aws_vpc"),
    # Internet Gateway → VPC
    ("aws_internet_gateway", "vpc_id", EdgeType.REFERENCES, "attached to", "aws_vpc"),
    # NAT Gateway → Subnet
    ("aws_nat_gateway", "subnet_id", EdgeType.REFERENCES, "in subnet", "aws_subnet"),
    # NAT Gateway → EIP
    ("aws_nat_gateway", "allocation_id", EdgeType.REFERENCES, "uses eip", "aws_eip"),
    # Security Group → VPC
    ("aws_security_group", "vpc_id", EdgeType.REFERENCES, "in vpc", "aws_vpc"),
    # Route Table → VPC
    ("aws_route_table", "vpc_id", EdgeType.REFERENCES, "in vpc", "aws_vpc"),
    # Route Table Association → Route Table
    (
        "aws_route_table_association",
        "route_table_id",
        EdgeType.REFERENCES,
        "associates route table",
        "aws_route_table",
    ),
    # Route Table Association → Subnet
    (
        "aws_route_table_association",
        "subnet_id",
        EdgeType.REFERENCES,
        "associates subnet",
        "aws_subnet",
    ),
    # API Gateway Deployment → REST API
    (
        "aws_api_gateway_deployment",
        "rest_api_id",
        EdgeType.REFERENCES,
        "deploys",
        "aws_api_gateway_rest_api",
    ),
    # API Gateway Stage → REST API
    (
        "aws_api_gateway_stage",
        "rest_api_id",
        EdgeType.REFERENCES,
        "stage of",
        "aws_api_gateway_rest_api",
    ),
    # API Gateway Stage → Deployment
    (
        "aws_api_gateway_stage",
        "deployment_id",
        EdgeType.REFERENCES,
        "uses deployment",
        "aws_api_gateway_deployment",
    ),
    # IAM Role Policy Attachment → Role
    (
        "aws_iam_role_policy_attachment",
        "role",
        EdgeType.REFERENCES,
        "attached to",
        "aws_iam_role",
    ),
    # IAM Role Policy → Role
    ("aws_iam_role_policy", "role", EdgeType.REFERENCES, "policy of", "aws_iam_role"),
    # Step Functions → IAM Role
    (
        "aws_sfn_state_machine",
        "role_arn",
        EdgeType.AUTHENTICATES,
        "assumes role",
        "aws_iam_role",
    ),
    # CloudWatch Log Group (matched by name pattern to Lambda)
    # Handled specially below
    # Flow Log → VPC
    ("aws_flow_log", "vpc_id", EdgeType.REFERENCES, "logs", "aws_vpc"),
    # VPC Peering
    (
        "aws_vpc_peering_connection",
        "vpc_id",
        EdgeType.REFERENCES,
        "peers from",
        "aws_vpc",
    ),
    (
        "aws_vpc_peering_connection",
        "peer_vpc_id",
        EdgeType.REFERENCES,
        "peers to",
        "aws_vpc",
    ),
    # EventBridge Rule → Target
    (
        "aws_cloudwatch_event_target",
        "rule",
        EdgeType.REFERENCES,
        "target of",
        "aws_cloudwatch_event_rule",
    ),
    (
        "aws_cloudwatch_event_target",
        "arn",
        EdgeType.TRIGGERS,
        "triggers",
        None,
    ),
    # Kinesis → Lambda (event source mapping handled via lambda_permission)
    (
        "aws_kinesis_firehose_delivery_stream",
        "kinesis_source_configuration.0.kinesis_stream_arn",
        EdgeType.READS_FROM,
        "reads from",
        "aws_kinesis_stream",
    ),
    # Cognito User Pool Client → User Pool
    (
        "aws_cognito_user_pool_client",
        "user_pool_id",
        EdgeType.REFERENCES,
        "client of",
        "aws_cognito_user_pool",
    ),
    # Cognito Identity Pool → User Pool
    (
        "aws_cognito_identity_pool",
        "cognito_identity_providers.*.client_id",
        EdgeType.REFERENCES,
        "federated with",
        None,
    ),
    # WAF → ALB association
    (
        "aws_wafv2_web_acl_association",
        "web_acl_arn",
        EdgeType.REFERENCES,
        "uses acl",
        "aws_wafv2_web_acl",
    ),
    (
        "aws_wafv2_web_acl_association",
        "resource_arn",
        EdgeType.REFERENCES,
        "protects",
        None,
    ),
    # ElastiCache Replication Group → Subnet Group
    (
        "aws_elasticache_replication_group",
        "subnet_group_name",
        EdgeType.REFERENCES,
        "in subnet group",
        None,
    ),
    # AppSync → Data Sources
    (
        "aws_appsync_datasource",
        "api_id",
        EdgeType.REFERENCES,
        "data source of",
        "aws_appsync_graphql_api",
    ),
    # Secrets Manager Secret Version → Secret
    (
        "aws_secretsmanager_secret_version",
        "secret_id",
        EdgeType.REFERENCES,
        "version of",
        "aws_secretsmanager_secret",
    ),
    # S3 Notification → Lambda / SQS / SNS
    (
        "aws_s3_bucket_notification",
        "lambda_function.*.lambda_function_arn",
        EdgeType.TRIGGERS,
        "notifies",
        "aws_lambda_function",
    ),
    (
        "aws_s3_bucket_notification",
        "queue.*.queue_arn",
        EdgeType.TRIGGERS,
        "notifies",
        "aws_sqs_queue",
    ),
    (
        "aws_s3_bucket_notification",
        "topic.*.topic_arn",
        EdgeType.TRIGGERS,
        "notifies",
        "aws_sns_topic",
    ),
    # SQS Queue → DLQ
    (
        "aws_sqs_queue",
        "redrive_policy",
        EdgeType.REFERENCES,
        "dead letter queue",
        None,
    ),
    # APIGateway V2 → Lambda integration
    (
        "aws_apigatewayv2_api",
        "target",
        EdgeType.TRIGGERS,
        "triggers",
        None,
    ),
    # ECR → ECS (resolved via task definition image)
    # ECS Task Definition → ECR (handled via IAM or image attribute)
    (
        "aws_ecs_task_definition",
        "container_definitions",
        EdgeType.REFERENCES,
        "pulls from",
        None,
    ),
]


_SECONDARY_RESOURCE_TYPES = {
    "aws_lambda_permission",
    "aws_iam_role_policy_attachment",
    "aws_iam_role_policy",
    "aws_api_gateway_deployment",
    "aws_api_gateway_stage",
    "aws_route_table_association",
    "aws_lb_listener",
    "aws_lb_listener_rule",
    "aws_s3_bucket_policy",
    "aws_s3_bucket_versioning",
    "aws_s3_bucket_server_side_encryption_configuration",
    "aws_s3_bucket_public_access_block",
    "aws_sns_topic_subscription",
    "aws_db_subnet_group",
    "aws_elasticache_subnet_group",
    "aws_flow_log",
    "aws_cloudwatch_event_target",
    "aws_secretsmanager_secret_version",
    "aws_cognito_user_pool_client",
    "aws_wafv2_web_acl_association",
    "aws_acm_certificate_validation",
    "aws_s3_bucket_website_configuration",
    "aws_s3_bucket_cors_configuration",
    "aws_s3_bucket_lifecycle_configuration",
    "aws_s3_bucket_notification",
    "aws_ecr_lifecycle_policy",
    "aws_appsync_resolver",
    "aws_appsync_datasource",
}


class TerraformParser(BaseParser):
    """Parser for Terraform state files (v4 format)."""

    def parse(self, source_path: str) -> StackMapIR:
        state = json.loads(Path(source_path).read_text())
        tf_version = state.get("terraform_version", "unknown")

        nodes: list[StackMapNode] = []
        edges: list[StackMapEdge] = []
        groups: list[StackMapGroup] = []

        # Indexes for relationship resolution
        id_index: dict[str, str] = {}  # attribute value → node_id
        arn_index: dict[str, str] = {}  # ARN → node_id
        node_map: dict[str, StackMapNode] = {}  # node_id → node

        # Pass 1: Extract nodes
        for resource in state.get("resources", []):
            if resource.get("mode") != "managed":
                continue

            resource_type = resource["type"]
            resource_name = resource["name"]
            provider = _extract_provider(resource.get("provider", ""))
            module = resource.get("module")

            for instance in resource.get("instances", []):
                attrs = instance.get("attributes", {})
                index_key = instance.get("index_key")

                node_id = _build_node_id(module, resource_type, resource_name, index_key)
                display_name = _resolve_name(resource_type, resource_name, attrs)
                category = RESOURCE_CATEGORY_MAP.get(resource_type, ResourceCategory.OTHER)
                tier = TIER_MAP.get(category, "backend")
                weight = WEIGHT_MAP.get(resource_type, 2)

                tags = attrs.get("tags") or attrs.get("tags_all") or {}
                if not isinstance(tags, dict):
                    tags = {}

                node = StackMapNode(
                    id=node_id,
                    name=display_name,
                    resource_type=resource_type,
                    provider=provider,
                    category=category,
                    properties=attrs,
                    tags=tags,
                    position_hint={"tier": tier, "weight": weight},
                )
                nodes.append(node)
                node_map[node_id] = node

                # Build indexes for relationship resolution
                for key in ["id", "arn", "execution_arn"]:
                    val = attrs.get(key)
                    if val and isinstance(val, str):
                        id_index[val] = node_id
                        if key in ("arn", "execution_arn"):
                            arn_index[val] = node_id

                # Index by function_name, bucket, name etc. — but only for
                # "primary" resource types (not permissions, attachments, etc.)
                # to avoid overwriting primary resources in the index
                if resource_type not in _SECONDARY_RESOURCE_TYPES:
                    for key in NAME_ATTRIBUTES:
                        val = attrs.get(key)
                        if val and isinstance(val, str):
                            id_index.setdefault(val, node_id)

        # Pass 2: Infer relationships
        edge_set: set[tuple[str, str, str]] = set()  # (source, target, edge_type) for dedup

        for node in nodes:
            attrs = node.properties

            # Apply relationship rules
            for rule_type, attr_path, edge_type, label, target_filter in RELATIONSHIP_RULES:
                if node.resource_type != rule_type:
                    continue

                values = _resolve_attribute_path(attrs, attr_path)
                for val in values:
                    target_id = _lookup_target(val, id_index, arn_index)
                    if target_id and target_id != node.id:
                        # Apply target type filter if specified
                        if target_filter and target_id in node_map:
                            if node_map[target_id].resource_type != target_filter:
                                continue
                        edge_key = (node.id, target_id, edge_type.value)
                        if edge_key not in edge_set:
                            edge_set.add(edge_key)
                            edges.append(
                                StackMapEdge(
                                    id=f"{node.id}->{target_id}",
                                    source=node.id,
                                    target=target_id,
                                    edge_type=edge_type,
                                    label=label,
                                )
                            )

            # Special: Lambda permission → creates edge from source to function
            if node.resource_type == "aws_lambda_permission":
                func_name = attrs.get("function_name", "")
                source_arn = attrs.get("source_arn", "")
                func_target = _lookup_target(func_name, id_index, arn_index)
                source_target = _lookup_target_prefix(source_arn, arn_index)
                if func_target and source_target and func_target != source_target:
                    edge_key = (source_target, func_target, EdgeType.TRIGGERS.value)
                    if edge_key not in edge_set:
                        edge_set.add(edge_key)
                        edges.append(
                            StackMapEdge(
                                id=f"{source_target}->{func_target}",
                                source=source_target,
                                target=func_target,
                                edge_type=EdgeType.TRIGGERS,
                                label="triggers",
                            )
                        )

            # Special: CloudFront → origins (S3, ALB)
            if node.resource_type == "aws_cloudfront_distribution":
                origins = attrs.get("origin", [])
                if isinstance(origins, list):
                    for origin in origins:
                        if isinstance(origin, dict):
                            domain = origin.get("domain_name", "")
                            target_id = _lookup_origin_target(domain, id_index, nodes)
                            if target_id and target_id != node.id:
                                edge_key = (node.id, target_id, EdgeType.ROUTES_TO.value)
                                if edge_key not in edge_set:
                                    edge_set.add(edge_key)
                                    edges.append(
                                        StackMapEdge(
                                            id=f"{node.id}->{target_id}",
                                            source=node.id,
                                            target=target_id,
                                            edge_type=EdgeType.ROUTES_TO,
                                            label="routes to origin",
                                        )
                                    )

                            # CloudFront Origin Access Control linkage
                            oac_id = origin.get("origin_access_control_id", "")
                            oac_target = _lookup_target(oac_id, id_index, arn_index)
                            if oac_target and oac_target != node.id:
                                edge_key = (node.id, oac_target, EdgeType.REFERENCES.value)
                                if edge_key not in edge_set:
                                    edge_set.add(edge_key)
                                    edges.append(
                                        StackMapEdge(
                                            id=f"{node.id}->{oac_target}",
                                            source=node.id,
                                            target=oac_target,
                                            edge_type=EdgeType.REFERENCES,
                                            label="uses oac",
                                        )
                                    )

                # CloudFront viewer certificate linkage to ACM certificate
                viewer_cert = attrs.get("viewer_certificate", [])
                if isinstance(viewer_cert, list):
                    for cert in viewer_cert:
                        if not isinstance(cert, dict):
                            continue
                        cert_arn = cert.get("acm_certificate_arn", "")
                        cert_target = _lookup_target(cert_arn, id_index, arn_index)
                        if cert_target and cert_target != node.id:
                            edge_key = (node.id, cert_target, EdgeType.REFERENCES.value)
                            if edge_key not in edge_set:
                                edge_set.add(edge_key)
                                edges.append(
                                    StackMapEdge(
                                        id=f"{node.id}->{cert_target}",
                                        source=node.id,
                                        target=cert_target,
                                        edge_type=EdgeType.REFERENCES,
                                        label="uses tls cert",
                                    )
                                )

            # Special: Route53 → alias targets (CloudFront, ALB)
            if node.resource_type == "aws_route53_record":
                aliases = attrs.get("alias", [])
                if isinstance(aliases, list):
                    for alias in aliases:
                        if isinstance(alias, dict):
                            name = alias.get("name", "")
                            target_id = _lookup_origin_target(name, id_index, nodes)
                            if target_id and target_id != node.id:
                                edge_key = (node.id, target_id, EdgeType.ROUTES_TO.value)
                                if edge_key not in edge_set:
                                    edge_set.add(edge_key)
                                    edges.append(
                                        StackMapEdge(
                                            id=f"{node.id}->{target_id}",
                                            source=node.id,
                                            target=target_id,
                                            edge_type=EdgeType.ROUTES_TO,
                                            label="routes to",
                                        )
                                    )

            # Special: CloudWatch Log Group → Lambda (by naming convention)
            if node.resource_type == "aws_cloudwatch_log_group":
                log_name = attrs.get("name", "")
                if log_name.startswith("/aws/lambda/"):
                    func_name = log_name.removeprefix("/aws/lambda/")
                    target_id = _lookup_target(func_name, id_index, arn_index)
                    if target_id and target_id != node.id:
                        edge_key = (target_id, node.id, EdgeType.REFERENCES.value)
                        if edge_key not in edge_set:
                            edge_set.add(edge_key)
                            edges.append(
                                StackMapEdge(
                                    id=f"{target_id}->{node.id}",
                                    source=target_id,
                                    target=node.id,
                                    edge_type=EdgeType.REFERENCES,
                                    label="logs to",
                                )
                            )

            # Special: S3 bucket policy can reference CloudFront distribution SourceArn
            if node.resource_type == "aws_s3_bucket_policy":
                bucket_name = attrs.get("bucket", "")
                bucket_target = _lookup_target(bucket_name, id_index, arn_index)
                policy_str = attrs.get("policy", "")
                if bucket_target and isinstance(policy_str, str) and policy_str:
                    try:
                        policy = json.loads(policy_str)
                    except (json.JSONDecodeError, TypeError):
                        policy = {}
                    for statement in policy.get("Statement", []):
                        if not isinstance(statement, dict):
                            continue
                        condition = statement.get("Condition", {})
                        if not isinstance(condition, dict):
                            continue
                        string_equals = condition.get("StringEquals", {})
                        if not isinstance(string_equals, dict):
                            continue
                        source_arn = string_equals.get("AWS:SourceArn", "")
                        cf_target = _lookup_target(source_arn, id_index, arn_index)
                        if cf_target and cf_target != bucket_target:
                            edge_key = (cf_target, bucket_target, EdgeType.ROUTES_TO.value)
                            if edge_key not in edge_set:
                                edge_set.add(edge_key)
                                edges.append(
                                    StackMapEdge(
                                        id=f"{cf_target}->{bucket_target}",
                                        source=cf_target,
                                        target=bucket_target,
                                        edge_type=EdgeType.ROUTES_TO,
                                        label="serves from bucket",
                                    )
                                )

        # Pass 3: Parse embedded definitions (Step Functions ASL, IAM policies)
        self._parse_step_function_definitions(nodes, edges, edge_set, arn_index, node_map)
        self._parse_iam_policies(nodes, edges, edge_set, arn_index, id_index, node_map)

        # Pass 3.5: mark helper resources for architecture-mode collapse
        self._mark_logical_helpers(nodes, id_index, arn_index)

        # Pass 4: Extract groups (VPCs, subnets)
        groups = self._extract_groups(nodes, id_index)

        return StackMapIR(
            metadata={
                "source_type": "terraform",
                "terraform_version": tf_version,
                "total_resources": len(nodes),
                "has_logical_helpers": True,
            },
            nodes=nodes,
            edges=edges,
            groups=groups,
        )

    def _parse_step_function_definitions(
        self,
        nodes: list[StackMapNode],
        edges: list[StackMapEdge],
        edge_set: set[tuple[str, str, str]],
        arn_index: dict[str, str],
        node_map: dict[str, StackMapNode],
    ) -> None:
        """Extract Lambda invocations from Step Functions ASL definitions."""
        for node in nodes:
            if node.resource_type != "aws_sfn_state_machine":
                continue
            defn_str = node.properties.get("definition", "")
            if not defn_str or not isinstance(defn_str, str):
                continue
            try:
                defn = json.loads(defn_str)
            except (json.JSONDecodeError, TypeError):
                continue

            # Walk all states and extract Resource ARNs from Task states
            lambda_arns = _extract_task_resources(defn)
            for arn in lambda_arns:
                target_id = arn_index.get(arn)
                if target_id and target_id != node.id:
                    edge_key = (node.id, target_id, EdgeType.TRIGGERS.value)
                    if edge_key not in edge_set:
                        edge_set.add(edge_key)
                        edges.append(
                            StackMapEdge(
                                id=f"{node.id}->{target_id}",
                                source=node.id,
                                target=target_id,
                                edge_type=EdgeType.TRIGGERS,
                                label="invokes",
                            )
                        )

    def _parse_iam_policies(
        self,
        nodes: list[StackMapNode],
        edges: list[StackMapEdge],
        edge_set: set[tuple[str, str, str]],
        arn_index: dict[str, str],
        id_index: dict[str, str],
        node_map: dict[str, StackMapNode],
    ) -> None:
        """Extract resource references from IAM role policies to infer data flow."""
        for node in nodes:
            if node.resource_type != "aws_iam_role_policy":
                continue

            policy_str = node.properties.get("policy", "")
            if not policy_str or not isinstance(policy_str, str):
                continue
            try:
                policy = json.loads(policy_str)
            except (json.JSONDecodeError, TypeError):
                continue

            # Find which compute resource uses this role
            role_name = node.properties.get("role", "")
            role_node_id = _lookup_target(role_name, id_index, arn_index)
            if not role_node_id:
                continue

            # Find the compute resource that assumes this role
            compute_node_id = None
            for n in nodes:
                if n.resource_type in (
                    "aws_lambda_function",
                    "aws_ecs_service",
                    "aws_sfn_state_machine",
                ):
                    role_ref = n.properties.get("role", "") or n.properties.get(
                        "role_arn", ""
                    )
                    role_target = _lookup_target(role_ref, id_index, arn_index)
                    if role_target == role_node_id:
                        compute_node_id = n.id
                        break

            if not compute_node_id:
                continue

            # Parse policy statements
            for statement in policy.get("Statement", []):
                if statement.get("Effect") != "Allow":
                    continue
                actions = statement.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                resources = statement.get("Resource", [])
                if isinstance(resources, str):
                    resources = [resources]

                edge_type = _classify_actions(actions)
                if edge_type is None:
                    continue

                for resource_arn in resources:
                    # Strip wildcard suffixes for matching
                    clean_arn = resource_arn.rstrip("/*").rstrip("*")
                    target_id = _lookup_target(clean_arn, id_index, arn_index)
                    if target_id and target_id != compute_node_id:
                        # Skip logs:* edges — already handled by log group naming
                        target_node = node_map.get(target_id)
                        if target_node and target_node.resource_type in (
                            "aws_cloudwatch_log_group",
                        ):
                            continue
                        edge_key = (compute_node_id, target_id, edge_type.value)
                        if edge_key not in edge_set:
                            edge_set.add(edge_key)
                            edges.append(
                                StackMapEdge(
                                    id=f"{compute_node_id}->{target_id}",
                                    source=compute_node_id,
                                    target=target_id,
                                    edge_type=edge_type,
                                    label=_action_label(actions),
                                )
                            )

    def _extract_groups(
        self,
        nodes: list[StackMapNode],
        id_index: dict[str, str],
    ) -> list[StackMapGroup]:
        """Extract VPC and subnet groups from nodes."""
        groups: list[StackMapGroup] = []
        vpc_nodes = [n for n in nodes if n.resource_type == "aws_vpc"]
        subnet_nodes = [n for n in nodes if n.resource_type == "aws_subnet"]

        # Build VPC ID → node ID mapping
        vpc_id_map: dict[str, str] = {}
        for node in vpc_nodes:
            vpc_id = node.properties.get("id", "")
            if vpc_id:
                vpc_id_map[vpc_id] = node.id

        # Create VPC groups
        for vpc_node in vpc_nodes:
            vpc_id = vpc_node.properties.get("id", "")
            children: list[str] = []

            # Find all resources in this VPC
            for node in nodes:
                if node.id == vpc_node.id:
                    continue
                attrs = node.properties
                # Direct vpc_id reference
                if attrs.get("vpc_id") == vpc_id:
                    children.append(node.id)

            groups.append(
                StackMapGroup(
                    id=f"group:{vpc_node.id}",
                    name=vpc_node.name,
                    group_type="vpc",
                    children=sorted(set(children)),
                    parent=None,
                )
            )

        # Create subnet groups (children of VPC groups)
        for subnet_node in subnet_nodes:
            subnet_id = subnet_node.properties.get("id", "")
            vpc_id = subnet_node.properties.get("vpc_id", "")
            parent_group = f"group:{vpc_id_map.get(vpc_id, '')}" if vpc_id in vpc_id_map else None

            children = []
            for node in nodes:
                if node.id == subnet_node.id:
                    continue
                attrs = node.properties
                # Check subnet_ids in various attribute paths
                subnet_ids = attrs.get("subnet_ids", [])
                if isinstance(subnet_ids, list) and subnet_id in subnet_ids:
                    children.append(node.id)
                # Check subnets attribute (used by ALBs)
                subnets = attrs.get("subnets", [])
                if isinstance(subnets, list) and subnet_id in subnets:
                    children.append(node.id)
                # Check subnet_id (singular, used by NAT gateways)
                if attrs.get("subnet_id") == subnet_id:
                    children.append(node.id)
                # Check network_configuration for ECS services
                net_config = attrs.get("network_configuration", [])
                if isinstance(net_config, list):
                    for nc in net_config:
                        if isinstance(nc, dict):
                            nc_subnets = nc.get("subnets", [])
                            if isinstance(nc_subnets, list) and subnet_id in nc_subnets:
                                children.append(node.id)
                # Check vpc_config for Lambda functions
                vpc_config = attrs.get("vpc_config", [])
                if isinstance(vpc_config, list):
                    for vc in vpc_config:
                        if isinstance(vc, dict):
                            vc_subnets = vc.get("subnet_ids", [])
                            if isinstance(vc_subnets, list) and subnet_id in vc_subnets:
                                children.append(node.id)

            if children:
                groups.append(
                    StackMapGroup(
                        id=f"group:{subnet_node.id}",
                        name=subnet_node.name,
                        group_type="subnet",
                        children=sorted(set(children)),
                        parent=parent_group,
                    )
                )

        return groups

    def _mark_logical_helpers(
        self,
        nodes: list[StackMapNode],
        id_index: dict[str, str],
        arn_index: dict[str, str],
    ) -> None:
        """Mark helper resources so UI can collapse them into logical parents."""
        node_by_id = {n.id: n for n in nodes}

        def _assign(node: StackMapNode, parent_id: str | None) -> None:
            node.position_hint["is_helper"] = True
            if parent_id and parent_id in node_by_id:
                node.position_hint["logical_parent"] = parent_id
                node.position_hint["weight"] = max(1, int(node.position_hint.get("weight", 2)) - 1)

        for node in nodes:
            attrs = node.properties
            parent_id: str | None = None

            if node.resource_type in {
                "aws_s3_bucket_policy",
                "aws_s3_bucket_versioning",
                "aws_s3_bucket_server_side_encryption_configuration",
                "aws_s3_bucket_public_access_block",
            }:
                bucket_name = attrs.get("bucket", "")
                parent_id = _lookup_target(bucket_name, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type in {"aws_iam_role_policy", "aws_iam_role_policy_attachment"}:
                role_name = attrs.get("role", "")
                parent_id = _lookup_target(role_name, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_api_gateway_deployment":
                rest_api_id = attrs.get("rest_api_id", "")
                parent_id = _lookup_target(rest_api_id, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_api_gateway_stage":
                deployment_id = attrs.get("deployment_id", "")
                rest_api_id = attrs.get("rest_api_id", "")
                parent_id = _lookup_target(rest_api_id, id_index, arn_index) or _lookup_target(
                    deployment_id, id_index, arn_index
                )
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_lambda_permission":
                function_name = attrs.get("function_name", "")
                parent_id = _lookup_target(function_name, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_cloudwatch_log_group":
                log_name = attrs.get("name", "")
                if isinstance(log_name, str) and log_name.startswith("/aws/lambda/"):
                    function_name = log_name.removeprefix("/aws/lambda/")
                    parent_id = _lookup_target(function_name, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_sns_topic_subscription":
                topic_arn = attrs.get("topic_arn", "")
                parent_id = _lookup_target(topic_arn, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_lb_listener":
                lb_arn = attrs.get("load_balancer_arn", "")
                parent_id = _lookup_target(lb_arn, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_lb_listener_rule":
                listener_arn = attrs.get("listener_arn", "")
                parent_id = _lookup_target(listener_arn, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type in {
                "aws_s3_bucket_website_configuration",
                "aws_s3_bucket_cors_configuration",
                "aws_s3_bucket_lifecycle_configuration",
                "aws_s3_bucket_notification",
            }:
                bucket_name = attrs.get("bucket", "")
                parent_id = _lookup_target(bucket_name, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_secretsmanager_secret_version":
                secret_id = attrs.get("secret_id", "")
                parent_id = _lookup_target(secret_id, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_cognito_user_pool_client":
                pool_id = attrs.get("user_pool_id", "")
                parent_id = _lookup_target(pool_id, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_wafv2_web_acl_association":
                acl_arn = attrs.get("web_acl_arn", "")
                parent_id = _lookup_target(acl_arn, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_acm_certificate_validation":
                cert_arn = attrs.get("certificate_arn", "")
                parent_id = _lookup_target(cert_arn, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_cloudwatch_event_target":
                rule_name = attrs.get("rule", "")
                parent_id = _lookup_target(rule_name, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_ecr_lifecycle_policy":
                repo = attrs.get("repository", "")
                parent_id = _lookup_target(repo, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_appsync_datasource":
                api_id = attrs.get("api_id", "")
                parent_id = _lookup_target(api_id, id_index, arn_index)
                _assign(node, parent_id)
                continue

            if node.resource_type == "aws_appsync_resolver":
                api_id = attrs.get("api_id", "")
                parent_id = _lookup_target(api_id, id_index, arn_index)
                _assign(node, parent_id)
                continue


def _lookup_target(
    value: str, id_index: dict[str, str], arn_index: dict[str, str]
) -> str | None:
    """Look up a node ID from an attribute value (ID, ARN, or name)."""
    if value in id_index:
        return id_index[value]
    if value in arn_index:
        return arn_index[value]
    return None


def _lookup_target_prefix(
    value: str, arn_index: dict[str, str]
) -> str | None:
    """Look up a node by ARN prefix match (for API Gateway execution ARNs etc.)."""
    # API Gateway execution ARNs look like:
    # arn:aws:execute-api:region:account:api-id/stage/method/path
    # We want to match the API Gateway REST API which has ARN:
    # arn:aws:execute-api:region:account:api-id
    if not value or not value.startswith("arn:"):
        return None

    # Exact prefix matching: longer ARN must start with shorter ARN
    # followed by a separator (/ or :) or be equal
    best_match: str | None = None
    best_len = 0
    for arn, node_id in arn_index.items():
        if value.startswith(arn) and len(arn) > best_len:
            # Ensure the match is at a boundary (end, or followed by / or :)
            if len(value) == len(arn) or value[len(arn)] in ("/", ":"):
                best_match = node_id
                best_len = len(arn)
        elif arn.startswith(value) and len(value) > best_len:
            if len(arn) == len(value) or arn[len(value)] in ("/", ":"):
                best_match = node_id
                best_len = len(value)

    return best_match


def _lookup_origin_target(
    domain: str, id_index: dict[str, str], nodes: list[StackMapNode]
) -> str | None:
    """Look up a node from a domain name (for CloudFront origins, Route53 aliases)."""
    if not domain:
        return None
    # Direct index lookup
    if domain in id_index:
        return id_index[domain]
    # Try matching S3 bucket names from domain
    # e.g. "bucket-name.s3.us-east-1.amazonaws.com" → "bucket-name"
    if ".s3." in domain:
        bucket_name = domain.split(".s3.")[0]
        if bucket_name in id_index:
            return id_index[bucket_name]
    # Try matching ALB DNS names
    # e.g. "main-alb-123456789.us-east-1.elb.amazonaws.com"
    if ".elb.amazonaws.com" in domain:
        for node in nodes:
            if node.resource_type in ("aws_lb", "aws_alb"):
                dns = node.properties.get("dns_name", "")
                if dns == domain:
                    return node.id
    # Try matching CloudFront domain
    if ".cloudfront.net" in domain:
        for node in nodes:
            if node.resource_type == "aws_cloudfront_distribution":
                cf_domain = node.properties.get("domain_name", "")
                if cf_domain == domain:
                    return node.id
    return None


def _extract_task_resources(defn: dict) -> list[str]:
    """Extract Lambda ARNs from Step Functions ASL definition."""
    arns: list[str] = []
    states = defn.get("States", {})
    for state in states.values():
        if not isinstance(state, dict):
            continue
        if state.get("Type") == "Task":
            resource = state.get("Resource", "")
            if isinstance(resource, str) and resource.startswith("arn:aws:lambda:"):
                arns.append(resource)
        # Handle Map and Parallel states (recursive)
        for key in ("Branches", "Iterator"):
            nested = state.get(key)
            if isinstance(nested, dict):
                arns.extend(_extract_task_resources(nested))
            elif isinstance(nested, list):
                for branch in nested:
                    if isinstance(branch, dict):
                        arns.extend(_extract_task_resources(branch))
    return arns


# Action classification for IAM policies
_WRITE_ACTIONS = {"PutItem", "UpdateItem", "DeleteItem", "BatchWriteItem", "PutObject",
                  "DeleteObject", "SendMessage", "Publish"}
_READ_ACTIONS = {"GetItem", "Query", "Scan", "GetObject", "ListBucket",
                 "ReceiveMessage", "GetQueueAttributes", "ListObjects"}
_INVOKE_ACTIONS = {"InvokeFunction", "Invoke"}


def _classify_actions(actions: list[str]) -> EdgeType | None:
    """Classify IAM actions into an edge type."""
    has_write = False
    has_read = False
    has_invoke = False

    for action in actions:
        # action format: "service:ActionName"
        parts = action.split(":")
        if len(parts) != 2:
            continue
        action_name = parts[1]
        # Skip log/monitoring actions
        if parts[0] in ("logs", "cloudwatch", "xray"):
            continue
        if action_name in _WRITE_ACTIONS:
            has_write = True
        elif action_name in _READ_ACTIONS:
            has_read = True
        elif action_name in _INVOKE_ACTIONS:
            has_invoke = True

    if has_invoke:
        return EdgeType.TRIGGERS
    if has_write and has_read:
        return EdgeType.WRITES_TO  # Write takes priority when both present
    if has_write:
        return EdgeType.WRITES_TO
    if has_read:
        return EdgeType.READS_FROM
    return None


def _action_label(actions: list[str]) -> str:
    """Generate a human-readable label from IAM actions."""
    services: set[str] = set()
    for action in actions:
        parts = action.split(":")
        if len(parts) == 2 and parts[0] not in ("logs", "cloudwatch", "xray"):
            services.add(parts[0])
    if not services:
        return "accesses"
    return ", ".join(sorted(services))
