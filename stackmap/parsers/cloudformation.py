"""CloudFormation template parser."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from stackmap.parsers.base import (
    BaseParser,
    EdgeType,
    ResourceCategory,
    StackMapEdge,
    StackMapGroup,
    StackMapIR,
    StackMapNode,
)

try:
    import yaml  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    yaml = None


CFN_CATEGORY_MAP: dict[str, ResourceCategory] = {
    "AWS::Lambda::Function": ResourceCategory.COMPUTE,
    "AWS::EC2::Instance": ResourceCategory.COMPUTE,
    "AWS::ECS::Cluster": ResourceCategory.CONTAINER,
    "AWS::ECS::Service": ResourceCategory.CONTAINER,
    "AWS::ECS::TaskDefinition": ResourceCategory.CONTAINER,
    "AWS::StepFunctions::StateMachine": ResourceCategory.INTEGRATION,
    "AWS::ApiGateway::RestApi": ResourceCategory.INTEGRATION,
    "AWS::ApiGateway::Deployment": ResourceCategory.INTEGRATION,
    "AWS::ApiGateway::Stage": ResourceCategory.INTEGRATION,
    "AWS::ApiGatewayV2::Api": ResourceCategory.INTEGRATION,
    "AWS::ApiGatewayV2::Integration": ResourceCategory.INTEGRATION,
    "AWS::ApiGatewayV2::Route": ResourceCategory.INTEGRATION,
    "AWS::ApiGatewayV2::Stage": ResourceCategory.INTEGRATION,
    "AWS::ApiGatewayV2::Authorizer": ResourceCategory.INTEGRATION,
    "AWS::S3::Bucket": ResourceCategory.STORAGE,
    "AWS::S3::BucketPolicy": ResourceCategory.SECURITY,
    "AWS::DynamoDB::Table": ResourceCategory.DATABASE,
    "AWS::RDS::DBInstance": ResourceCategory.DATABASE,
    "AWS::RDS::DBCluster": ResourceCategory.DATABASE,
    "AWS::EC2::VPC": ResourceCategory.NETWORK,
    "AWS::EC2::Subnet": ResourceCategory.NETWORK,
    "AWS::EC2::RouteTable": ResourceCategory.NETWORK,
    "AWS::EC2::SubnetRouteTableAssociation": ResourceCategory.NETWORK,
    "AWS::EC2::InternetGateway": ResourceCategory.NETWORK,
    "AWS::EC2::NatGateway": ResourceCategory.NETWORK,
    "AWS::EC2::EIP": ResourceCategory.NETWORK,
    "AWS::EC2::SecurityGroup": ResourceCategory.NETWORK,
    "AWS::ElasticLoadBalancingV2::LoadBalancer": ResourceCategory.NETWORK,
    "AWS::ElasticLoadBalancingV2::TargetGroup": ResourceCategory.NETWORK,
    "AWS::ElasticLoadBalancingV2::Listener": ResourceCategory.NETWORK,
    "AWS::ElasticLoadBalancingV2::ListenerRule": ResourceCategory.NETWORK,
    "AWS::IAM::Role": ResourceCategory.SECURITY,
    "AWS::IAM::Policy": ResourceCategory.SECURITY,
    "AWS::IAM::ManagedPolicy": ResourceCategory.SECURITY,
    "AWS::Lambda::Permission": ResourceCategory.SECURITY,
    "AWS::Cognito::UserPool": ResourceCategory.SECURITY,
    "AWS::Cognito::UserPoolClient": ResourceCategory.SECURITY,
    "AWS::Logs::LogGroup": ResourceCategory.MONITORING,
    "AWS::CloudWatch::Dashboard": ResourceCategory.MONITORING,
    "AWS::CloudFront::Distribution": ResourceCategory.CDN,
    "AWS::CloudFront::OriginAccessControl": ResourceCategory.CDN,
    "AWS::Lambda::LayerVersion": ResourceCategory.COMPUTE,
    "AWS::Route53::RecordSet": ResourceCategory.DNS,
    "AWS::Route53::RecordSetGroup": ResourceCategory.DNS,
    "AWS::SQS::Queue": ResourceCategory.QUEUE,
    "AWS::SNS::Topic": ResourceCategory.QUEUE,
    "AWS::SNS::Subscription": ResourceCategory.QUEUE,
    # EventBridge
    "AWS::Events::Rule": ResourceCategory.INTEGRATION,
    "AWS::Events::EventBus": ResourceCategory.INTEGRATION,
    "AWS::Scheduler::Schedule": ResourceCategory.INTEGRATION,
    # Kinesis
    "AWS::Kinesis::Stream": ResourceCategory.QUEUE,
    "AWS::KinesisFirehose::DeliveryStream": ResourceCategory.QUEUE,
    # Secrets & Config
    "AWS::SecretsManager::Secret": ResourceCategory.SECURITY,
    "AWS::SSM::Parameter": ResourceCategory.SECURITY,
    # Cognito
    "AWS::Cognito::IdentityPool": ResourceCategory.SECURITY,
    # WAF
    "AWS::WAFv2::WebACL": ResourceCategory.SECURITY,
    "AWS::WAFv2::WebACLAssociation": ResourceCategory.SECURITY,
    # ElastiCache
    "AWS::ElastiCache::CacheCluster": ResourceCategory.DATABASE,
    "AWS::ElastiCache::ReplicationGroup": ResourceCategory.DATABASE,
    "AWS::ElastiCache::SubnetGroup": ResourceCategory.DATABASE,
    # ACM
    "AWS::CertificateManager::Certificate": ResourceCategory.SECURITY,
    # AppSync
    "AWS::AppSync::GraphQLApi": ResourceCategory.INTEGRATION,
    "AWS::AppSync::DataSource": ResourceCategory.INTEGRATION,
    "AWS::AppSync::Resolver": ResourceCategory.INTEGRATION,
    # Step Functions
    "AWS::StepFunctions::Activity": ResourceCategory.INTEGRATION,
    # ECR
    "AWS::ECR::Repository": ResourceCategory.CONTAINER,
    # SES
    "AWS::SES::EmailIdentity": ResourceCategory.INTEGRATION,
    # SAM resources
    "AWS::Serverless::Function": ResourceCategory.COMPUTE,
    "AWS::Serverless::Api": ResourceCategory.INTEGRATION,
    "AWS::Serverless::HttpApi": ResourceCategory.INTEGRATION,
    "AWS::Serverless::StateMachine": ResourceCategory.INTEGRATION,
    "AWS::Serverless::SimpleTable": ResourceCategory.DATABASE,
    "AWS::Serverless::LayerVersion": ResourceCategory.COMPUTE,
    "AWS::Serverless::Application": ResourceCategory.OTHER,
}

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

WEIGHT_MAP: dict[str, int] = {
    "AWS::Lambda::Function": 5,
    "AWS::ApiGateway::RestApi": 5,
    "AWS::ApiGatewayV2::Api": 5,
    "AWS::StepFunctions::StateMachine": 5,
    "AWS::ECS::Service": 5,
    "AWS::ECS::Cluster": 4,
    "AWS::DynamoDB::Table": 5,
    "AWS::RDS::DBInstance": 5,
    "AWS::S3::Bucket": 4,
    "AWS::ElasticLoadBalancingV2::LoadBalancer": 5,
    "AWS::CloudFront::Distribution": 5,
    "AWS::EC2::VPC": 3,
    "AWS::EC2::Subnet": 2,
    "AWS::SQS::Queue": 4,
    "AWS::SNS::Topic": 4,
    "AWS::Events::Rule": 3,
    "AWS::Events::EventBus": 4,
    "AWS::Kinesis::Stream": 4,
    "AWS::KinesisFirehose::DeliveryStream": 4,
    "AWS::SecretsManager::Secret": 3,
    "AWS::Cognito::UserPool": 4,
    "AWS::WAFv2::WebACL": 3,
    "AWS::ElastiCache::CacheCluster": 5,
    "AWS::ElastiCache::ReplicationGroup": 5,
    "AWS::AppSync::GraphQLApi": 5,
    "AWS::ECR::Repository": 3,
    "AWS::RDS::DBCluster": 5,
    "AWS::Serverless::Function": 5,
    "AWS::Serverless::Api": 5,
    "AWS::Serverless::HttpApi": 5,
    "AWS::Serverless::StateMachine": 5,
    "AWS::Serverless::SimpleTable": 5,
}

_SUB_REF_PATTERN = re.compile(r"\${([A-Za-z0-9:_\-.]+)}")

_HELPER_TYPES = {
    "AWS::ApiGateway::Deployment",
    "AWS::ApiGateway::Stage",
    "AWS::ApiGateway::Method",
    "AWS::ApiGateway::Resource",
    "AWS::ApiGateway::Integration",
    "AWS::ApiGatewayV2::Integration",
    "AWS::ApiGatewayV2::Route",
    "AWS::ApiGatewayV2::Stage",
    "AWS::ApiGatewayV2::Authorizer",
    "AWS::Lambda::Permission",
    "AWS::Lambda::LayerVersion",
    "AWS::Logs::LogGroup",
    "AWS::CloudWatch::Dashboard",
    "AWS::IAM::Policy",
    "AWS::IAM::ManagedPolicy",
    "AWS::S3::BucketPolicy",
    "AWS::ElasticLoadBalancingV2::Listener",
    "AWS::ElasticLoadBalancingV2::ListenerRule",
    "AWS::ElasticLoadBalancingV2::TargetGroup",
    "AWS::EC2::RouteTable",
    "AWS::EC2::SubnetRouteTableAssociation",
    "AWS::EC2::EIP",
    "AWS::EC2::NatGateway",
    "AWS::Serverless::LayerVersion",
    "AWS::WAFv2::WebACLAssociation",
    "AWS::CertificateManager::Certificate",
    "AWS::ElastiCache::SubnetGroup",
    "AWS::AppSync::DataSource",
    "AWS::AppSync::Resolver",
    "AWS::ECR::Repository",
}

_CFN_INTRINSIC_SHORTCUTS = {
    "Base64",
    "Cidr",
    "FindInMap",
    "GetAZs",
    "GetAtt",
    "If",
    "ImportValue",
    "Join",
    "Select",
    "Split",
    "Sub",
    "Transform",
    "And",
    "Equals",
    "Not",
    "Or",
}


def _build_cfn_yaml_loader() -> Any:
    if yaml is None:
        return None

    class _CfnLoader(yaml.SafeLoader):  # type: ignore[misc, valid-type]
        pass

    def _cfn_multi_constructor(loader: Any, tag_suffix: str, node: Any) -> dict[str, Any]:
        if node.__class__.__name__ == "ScalarNode":
            value = loader.construct_scalar(node)
        elif node.__class__.__name__ == "SequenceNode":
            value = loader.construct_sequence(node)
        else:
            value = loader.construct_mapping(node)

        if tag_suffix == "Ref":
            key = "Ref"
        elif tag_suffix == "Condition":
            key = "Condition"
        elif tag_suffix.startswith("Fn::"):
            key = tag_suffix
        elif tag_suffix in _CFN_INTRINSIC_SHORTCUTS:
            key = f"Fn::{tag_suffix}"
        else:
            # Preserve unknown tags as-is to avoid data loss.
            key = tag_suffix
        return {key: value}

    _CfnLoader.add_multi_constructor("!", _cfn_multi_constructor)
    return _CfnLoader


def _parse_template(source_path: str) -> dict[str, Any]:
    content = Path(source_path).read_text()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        if yaml is None:
            raise ValueError(
                "YAML CloudFormation template detected but PyYAML is not installed. "
                "Install it with `pip install PyYAML` (or `pip install -e .`) "
                "or provide a JSON template."
            ) from None
        loader = _build_cfn_yaml_loader()
        data = yaml.load(content, Loader=loader)  # type: ignore[arg-type]
        if not isinstance(data, dict):
            raise ValueError("CloudFormation template root must be an object")
        return data


def _is_sam_transform(transform: Any) -> bool:
    if isinstance(transform, str):
        return transform == "AWS::Serverless-2016-10-31"
    if isinstance(transform, list):
        return any(isinstance(t, str) and t == "AWS::Serverless-2016-10-31" for t in transform)
    return False


def _resolve_name(logical_id: str, resource_type: str, props: dict[str, Any]) -> str:
    for key in (
        "FunctionName",
        "TableName",
        "BucketName",
        "RoleName",
        "QueueName",
        "TopicName",
        "ServiceName",
        "ClusterName",
        "DBInstanceIdentifier",
        "Name",
    ):
        val = props.get(key)
        if isinstance(val, str) and val:
            return val
    return logical_id if resource_type.startswith("AWS::") else f"{resource_type}:{logical_id}"


def _extract_tags(props: dict[str, Any]) -> dict[str, str]:
    tags = props.get("Tags", {})
    if isinstance(tags, dict):
        return {str(k): str(v) for k, v in tags.items()}
    if isinstance(tags, list):
        out: dict[str, str] = {}
        for t in tags:
            if isinstance(t, dict):
                key = t.get("Key")
                value = t.get("Value")
                if isinstance(key, str) and value is not None:
                    out[key] = str(value)
        return out
    return {}


def _iter_refs(value: Any) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if "Ref" in value and isinstance(value["Ref"], str):
            refs.append((value["Ref"], "ref"))
        if "Fn::GetAtt" in value:
            ga = value["Fn::GetAtt"]
            if isinstance(ga, list) and ga and isinstance(ga[0], str):
                refs.append((ga[0], "getatt"))
            elif isinstance(ga, str):
                refs.append((ga.split(".", 1)[0], "getatt"))
        if "Fn::Sub" in value:
            sub = value["Fn::Sub"]
            if isinstance(sub, str):
                for match in _SUB_REF_PATTERN.findall(sub):
                    refs.append((match.split(".", 1)[0], "sub"))
            elif isinstance(sub, list) and sub and isinstance(sub[0], str):
                for match in _SUB_REF_PATTERN.findall(sub[0]):
                    refs.append((match.split(".", 1)[0], "sub"))
        for child in value.values():
            refs.extend(_iter_refs(child))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_iter_refs(item))
    return refs


def _edge_type_for(source_type: str, target_type: str) -> EdgeType:
    if source_type in {"AWS::Lambda::Function", "AWS::Serverless::Function"} and target_type == "AWS::IAM::Role":
        return EdgeType.AUTHENTICATES
    if source_type == "AWS::EC2::Subnet" and target_type == "AWS::EC2::VPC":
        return EdgeType.CONTAINS
    if source_type in {"AWS::CloudFront::Distribution", "AWS::Route53::RecordSet"} and target_type in {
        "AWS::S3::Bucket",
        "AWS::ElasticLoadBalancingV2::LoadBalancer",
        "AWS::CloudFront::Distribution",
        "AWS::ApiGateway::RestApi",
    }:
        return EdgeType.ROUTES_TO
    if source_type in {
        "AWS::ApiGateway::Method",
        "AWS::ApiGatewayV2::Integration",
        "AWS::StepFunctions::StateMachine",
        "AWS::SNS::Topic",
        "AWS::SNS::Subscription",
        "AWS::Events::Rule",
        "AWS::ElasticLoadBalancingV2::Listener",
        "AWS::ElasticLoadBalancingV2::ListenerRule",
    } and target_type in {
        "AWS::Lambda::Function",
        "AWS::Serverless::Function",
    }:
        return EdgeType.TRIGGERS
    if source_type == "AWS::Events::Rule" and target_type in {
        "AWS::Lambda::Function",
        "AWS::Serverless::Function",
        "AWS::StepFunctions::StateMachine",
        "AWS::Serverless::StateMachine",
        "AWS::SQS::Queue",
        "AWS::SNS::Topic",
    }:
        return EdgeType.TRIGGERS
    if source_type in {"AWS::Kinesis::Stream", "AWS::DynamoDB::Table"} and target_type in {
        "AWS::Lambda::Function",
        "AWS::Serverless::Function",
    }:
        return EdgeType.TRIGGERS
    return EdgeType.REFERENCES


def _edge_label(kind: str, edge_type: EdgeType) -> str:
    if edge_type == EdgeType.AUTHENTICATES:
        return "assumes role"
    if edge_type == EdgeType.CONTAINS:
        return "in vpc"
    if edge_type == EdgeType.ROUTES_TO:
        return "routes to"
    if edge_type == EdgeType.TRIGGERS:
        return "triggers"
    if kind == "getatt":
        return "uses attribute"
    if kind == "sub":
        return "template reference"
    return "references"


class CloudFormationParser(BaseParser):
    """Parser for CloudFormation templates (JSON/YAML)."""

    def parse(self, source_path: str) -> StackMapIR:
        template = _parse_template(source_path)
        resources = template.get("Resources", {})
        if not isinstance(resources, dict):
            raise ValueError("CloudFormation template must contain an object Resources section")

        nodes: list[StackMapNode] = []
        edges: list[StackMapEdge] = []
        groups: list[StackMapGroup] = []
        node_by_id: dict[str, StackMapNode] = {}

        for logical_id, spec in resources.items():
            if not isinstance(spec, dict):
                continue
            resource_type = spec.get("Type", "")
            if not isinstance(resource_type, str) or not resource_type:
                continue
            props = spec.get("Properties", {})
            if not isinstance(props, dict):
                props = {}
            category = CFN_CATEGORY_MAP.get(resource_type, ResourceCategory.OTHER)
            node = StackMapNode(
                id=logical_id,
                name=_resolve_name(logical_id, resource_type, props),
                resource_type=resource_type,
                provider="aws",
                category=category,
                properties=props,
                tags=_extract_tags(props),
                position_hint={
                    "tier": TIER_MAP.get(category, "backend"),
                    "weight": WEIGHT_MAP.get(resource_type, 2),
                    "is_helper": resource_type in _HELPER_TYPES,
                },
            )
            nodes.append(node)
            node_by_id[logical_id] = node

        edge_keys: set[tuple[str, str, str]] = set()

        for logical_id, spec in resources.items():
            source_node = node_by_id.get(logical_id)
            if source_node is None or not isinstance(spec, dict):
                continue

            depends_on = spec.get("DependsOn")
            if isinstance(depends_on, str):
                depends = [depends_on]
            elif isinstance(depends_on, list):
                depends = [d for d in depends_on if isinstance(d, str)]
            else:
                depends = []

            refs = _iter_refs(spec.get("Properties", {}))
            refs.extend((d, "depends") for d in depends)

            for target_logical_id, ref_kind in refs:
                target = node_by_id.get(target_logical_id)
                if target is None or target.id == source_node.id:
                    continue
                edge_type = _edge_type_for(source_node.resource_type, target.resource_type)
                key = (source_node.id, target.id, edge_type.value)
                if key in edge_keys:
                    continue
                edge_keys.add(key)
                edges.append(
                    StackMapEdge(
                        id=f"{source_node.id}->{target.id}:{edge_type.value}",
                        source=source_node.id,
                        target=target.id,
                        edge_type=edge_type,
                        label=_edge_label(ref_kind, edge_type),
                    )
                )

            if source_node.resource_type == "AWS::Lambda::Permission":
                props = spec.get("Properties", {})
                if isinstance(props, dict):
                    function_ref = props.get("FunctionName")
                    source_arn = props.get("SourceArn")
                    func_targets = [r for r, _k in _iter_refs(function_ref)] if function_ref is not None else []
                    src_targets = [r for r, _k in _iter_refs(source_arn)] if source_arn is not None else []
                    for src in src_targets:
                        for tgt in func_targets:
                            src_node = node_by_id.get(src)
                            tgt_node = node_by_id.get(tgt)
                            if not src_node or not tgt_node or src_node.id == tgt_node.id:
                                continue
                            key = (src_node.id, tgt_node.id, EdgeType.TRIGGERS.value)
                            if key in edge_keys:
                                continue
                            edge_keys.add(key)
                            edges.append(
                                StackMapEdge(
                                    id=f"{src_node.id}->{tgt_node.id}:{EdgeType.TRIGGERS.value}",
                                    source=src_node.id,
                                    target=tgt_node.id,
                                    edge_type=EdgeType.TRIGGERS,
                                    label="triggers",
                                )
                            )

            # SAM: implicit event wiring (Events -> Function)
            if source_node.resource_type == "AWS::Serverless::Function":
                props = spec.get("Properties", {})
                if isinstance(props, dict):
                    events = props.get("Events")
                    if isinstance(events, dict):
                        for event in events.values():
                            if not isinstance(event, dict):
                                continue
                            event_type = event.get("Type")
                            event_props = event.get("Properties", {})
                            if not isinstance(event_props, dict):
                                event_props = {}

                            # Api/HttpApi event -> Function
                            if event_type in {"Api", "HttpApi"}:
                                api_ref_obj = event_props.get("RestApiId") or event_props.get("ApiId")
                                api_refs = _iter_refs(api_ref_obj) if api_ref_obj else []
                                for api_logical_id, _kind in api_refs:
                                    api_node = node_by_id.get(api_logical_id)
                                    if not api_node or api_node.id == source_node.id:
                                        continue
                                    key = (api_node.id, source_node.id, EdgeType.TRIGGERS.value)
                                    if key in edge_keys:
                                        continue
                                    edge_keys.add(key)
                                    edges.append(
                                        StackMapEdge(
                                            id=f"{api_node.id}->{source_node.id}:{EdgeType.TRIGGERS.value}",
                                            source=api_node.id,
                                            target=source_node.id,
                                            edge_type=EdgeType.TRIGGERS,
                                            label="triggers",
                                        )
                                    )

                            # SQS event -> Function
                            elif event_type == "SQS":
                                queue_ref = event_props.get("Queue")
                                for ref_id, _kind in _iter_refs(queue_ref) if queue_ref else []:
                                    q_node = node_by_id.get(ref_id)
                                    if q_node and q_node.id != source_node.id:
                                        key = (q_node.id, source_node.id, EdgeType.TRIGGERS.value)
                                        if key not in edge_keys:
                                            edge_keys.add(key)
                                            edges.append(StackMapEdge(
                                                id=f"{q_node.id}->{source_node.id}:{EdgeType.TRIGGERS.value}",
                                                source=q_node.id, target=source_node.id,
                                                edge_type=EdgeType.TRIGGERS, label="triggers",
                                            ))

                            # SNS event -> Function
                            elif event_type == "SNS":
                                topic_ref = event_props.get("Topic")
                                for ref_id, _kind in _iter_refs(topic_ref) if topic_ref else []:
                                    t_node = node_by_id.get(ref_id)
                                    if t_node and t_node.id != source_node.id:
                                        key = (t_node.id, source_node.id, EdgeType.TRIGGERS.value)
                                        if key not in edge_keys:
                                            edge_keys.add(key)
                                            edges.append(StackMapEdge(
                                                id=f"{t_node.id}->{source_node.id}:{EdgeType.TRIGGERS.value}",
                                                source=t_node.id, target=source_node.id,
                                                edge_type=EdgeType.TRIGGERS, label="triggers",
                                            ))

                            # DynamoDB Stream event -> Function
                            elif event_type == "DynamoDB":
                                stream_ref = event_props.get("Stream")
                                for ref_id, _kind in _iter_refs(stream_ref) if stream_ref else []:
                                    d_node = node_by_id.get(ref_id)
                                    if d_node and d_node.id != source_node.id:
                                        key = (d_node.id, source_node.id, EdgeType.TRIGGERS.value)
                                        if key not in edge_keys:
                                            edge_keys.add(key)
                                            edges.append(StackMapEdge(
                                                id=f"{d_node.id}->{source_node.id}:{EdgeType.TRIGGERS.value}",
                                                source=d_node.id, target=source_node.id,
                                                edge_type=EdgeType.TRIGGERS, label="stream triggers",
                                            ))

                            # Kinesis event -> Function
                            elif event_type == "Kinesis":
                                stream_ref = event_props.get("Stream")
                                for ref_id, _kind in _iter_refs(stream_ref) if stream_ref else []:
                                    k_node = node_by_id.get(ref_id)
                                    if k_node and k_node.id != source_node.id:
                                        key = (k_node.id, source_node.id, EdgeType.TRIGGERS.value)
                                        if key not in edge_keys:
                                            edge_keys.add(key)
                                            edges.append(StackMapEdge(
                                                id=f"{k_node.id}->{source_node.id}:{EdgeType.TRIGGERS.value}",
                                                source=k_node.id, target=source_node.id,
                                                edge_type=EdgeType.TRIGGERS, label="stream triggers",
                                            ))

                            # S3 event -> Function
                            elif event_type == "S3":
                                bucket_ref = event_props.get("Bucket")
                                for ref_id, _kind in _iter_refs(bucket_ref) if bucket_ref else []:
                                    b_node = node_by_id.get(ref_id)
                                    if b_node and b_node.id != source_node.id:
                                        key = (b_node.id, source_node.id, EdgeType.TRIGGERS.value)
                                        if key not in edge_keys:
                                            edge_keys.add(key)
                                            edges.append(StackMapEdge(
                                                id=f"{b_node.id}->{source_node.id}:{EdgeType.TRIGGERS.value}",
                                                source=b_node.id, target=source_node.id,
                                                edge_type=EdgeType.TRIGGERS, label="event triggers",
                                            ))

        self._mark_helper_parents(nodes, edges)
        groups = self._extract_groups(nodes, edges)

        is_sam = _is_sam_transform(template.get("Transform"))

        return StackMapIR(
            metadata={
                "source_type": "sam" if is_sam else "cloudformation",
                "template_format_version": str(template.get("AWSTemplateFormatVersion", "unknown")),
                "total_resources": len(nodes),
                "has_logical_helpers": True,
                "transform": template.get("Transform"),
            },
            nodes=nodes,
            edges=edges,
            groups=groups,
        )

    def _mark_helper_parents(self, nodes: list[StackMapNode], edges: list[StackMapEdge]) -> None:
        node_by_id = {n.id: n for n in nodes}
        adjacency: dict[str, set[str]] = {}
        for e in edges:
            adjacency.setdefault(e.source, set()).add(e.target)
            adjacency.setdefault(e.target, set()).add(e.source)

        def assign(node: StackMapNode, parent_id: str | None) -> None:
            node.position_hint["is_helper"] = True
            if parent_id and parent_id in node_by_id:
                node.position_hint["logical_parent"] = parent_id
                node.position_hint["weight"] = max(1, int(node.position_hint.get("weight", 2)) - 1)

        for node in nodes:
            if node.resource_type not in _HELPER_TYPES:
                continue
            neighbors = [nid for nid in adjacency.get(node.id, set()) if nid in node_by_id]
            if not neighbors:
                assign(node, None)
                continue
            neighbors_sorted = sorted(
                neighbors,
                key=lambda nid: (
                    node_by_id[nid].category.value in {"security", "monitoring"},
                    node_by_id[nid].name,
                ),
            )
            assign(node, neighbors_sorted[0])

    def _extract_groups(self, nodes: list[StackMapNode], edges: list[StackMapEdge]) -> list[StackMapGroup]:
        groups: list[StackMapGroup] = []
        by_id = {n.id: n for n in nodes}
        vpcs = [n for n in nodes if n.resource_type == "AWS::EC2::VPC"]
        for vpc in vpcs:
            children = [
                e.source
                for e in edges
                if e.target == vpc.id
                and e.source in by_id
                and by_id[e.source].resource_type == "AWS::EC2::Subnet"
            ]
            if children:
                groups.append(
                    StackMapGroup(
                        id=f"group:{vpc.id}",
                        name=vpc.name,
                        group_type="vpc",
                        children=sorted(set(children)),
                        parent=None,
                    )
                )
        return groups
