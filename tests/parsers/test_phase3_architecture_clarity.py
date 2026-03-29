"""Phase 3 quality gate: architecture projection clarity (noise down, story preserved)."""

from collections import defaultdict
from pathlib import Path

from stackmap.parsers.terraform import TerraformParser

FIXTURES = Path(__file__).parent.parent / "fixtures"

HELPER_RESOURCE_TYPES = {
    "aws_iam_role",
    "aws_iam_policy",
    "aws_iam_role_policy",
    "aws_iam_role_policy_attachment",
    "aws_cloudwatch_log_group",
    "aws_lambda_permission",
    "aws_sns_topic_subscription",
    "aws_cloudfront_origin_access_control",
    "aws_api_gateway_deployment",
    "aws_api_gateway_stage",
    "aws_api_gateway_method",
    "aws_api_gateway_resource",
    "aws_api_gateway_integration",
    "aws_lb_listener",
    "aws_lb_listener_rule",
    "aws_lb_target_group",
    "aws_db_subnet_group",
    "aws_elasticache_subnet_group",
    "aws_s3_bucket_policy",
    "aws_s3_bucket_versioning",
    "aws_s3_bucket_server_side_encryption_configuration",
    "aws_route_table",
    "aws_route_table_association",
    "aws_eip",
    "aws_flow_log",
    "aws_security_group",
    "aws_acm_certificate",
    "aws_s3_bucket_public_access_block",
    "aws_s3_bucket_website_configuration",
    "aws_s3_bucket_cors_configuration",
    "aws_s3_bucket_lifecycle_configuration",
    "aws_s3_bucket_notification",
    "aws_nat_gateway",
    "aws_internet_gateway",
}

ARCH_DROPPED_EDGE_TYPES = {"authenticates", "contains"}
REFERENCE_TYPE_ALLOWLIST = {
    "aws_ecs_service->aws_ecs_cluster",
    "aws_ecs_service->aws_ecs_task_definition",
    "aws_ecs_service->aws_lb_target_group",
    "aws_lb->aws_subnet",
    "aws_lb->aws_vpc",
    "aws_lb_listener->aws_lb_target_group",
    "aws_lb_listener_rule->aws_lb_target_group",
    "aws_lambda_function->aws_subnet",
    "aws_lambda_function->aws_vpc",
    "aws_nat_gateway->aws_eip",
    "aws_route_table_association->aws_route_table",
    "aws_route_table_association->aws_subnet",
    "aws_api_gateway_stage->aws_api_gateway_deployment",
    "aws_route53_record->aws_route53_zone",
}

PRIMARY_CATEGORY_PRIORITY = {
    "serverless": 0,
    "compute": 1,
    "container": 2,
    "integration": 3,
    "queue": 4,
    "database": 5,
    "storage": 6,
    "network": 7,
    "cdn": 8,
    "dns": 9,
    "monitoring": 10,
    "other": 20,
    "security": 30,
}


def _is_helper(node: dict) -> bool:
    hint = node.get("position_hint") or {}
    if hint.get("is_helper"):
        return True
    return node.get("resource_type") in HELPER_RESOURCE_TYPES


def _pick_best_primary(nodes_by_id: dict, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda nid: (
            PRIMARY_CATEGORY_PRIORITY.get(
                getattr(nodes_by_id.get(nid, {}).get("category"), "value", nodes_by_id.get(nid, {}).get("category")),
                100,
            ),
            nodes_by_id.get(nid, {}).get("name", nid),
        ),
    )[0]


def _should_keep_reference_edge(source: dict | None, target: dict | None) -> bool:
    if not source or not target:
        return False

    pair = f"{source['resource_type']}->{target['resource_type']}"
    if pair in REFERENCE_TYPE_ALLOWLIST:
        return True

    source_cat = getattr(source.get("category"), "value", source.get("category"))
    target_cat = getattr(target.get("category"), "value", target.get("category"))

    source_is_compute_like = source_cat in {
        "compute",
        "container",
        "integration",
        "serverless",
    }
    target_is_data_like = target_cat in {"database", "storage", "queue"}
    if source_is_compute_like and target_is_data_like:
        return True

    source_is_entry = source_cat in {"cdn", "dns", "network", "integration"}
    target_is_core = target_cat in {
        "compute",
        "container",
        "integration",
        "database",
        "storage",
        "queue",
    }
    return source_is_entry and target_is_core


def _project_architecture(ir) -> tuple[list[dict], list[dict]]:
    nodes = [n.__dict__ for n in ir.nodes]
    edges = [e.__dict__ for e in ir.edges]
    nodes_by_id = {n["id"]: n for n in nodes}
    helper_ids = {n["id"] for n in nodes if _is_helper(n)}

    adjacency: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        adjacency[e["source"]].add(e["target"])
        adjacency[e["target"]].add(e["source"])

    parent_map: dict[str, str] = {}

    for n in nodes:
        explicit = (n.get("position_hint") or {}).get("logical_parent")
        if explicit:
            parent_map[n["id"]] = explicit

    for n in nodes:
        if n["id"] in parent_map or n["id"] not in helper_ids:
            continue
        direct_primary = [nid for nid in adjacency.get(n["id"], set()) if nid not in helper_ids]
        first = _pick_best_primary(nodes_by_id, direct_primary)
        if first:
            parent_map[n["id"]] = first
            continue

        depth_two = set()
        for n1 in adjacency.get(n["id"], set()):
            for n2 in adjacency.get(n1, set()):
                if n2 not in helper_ids:
                    depth_two.add(n2)
        second = _pick_best_primary(nodes_by_id, list(depth_two))
        if second:
            parent_map[n["id"]] = second

    graph_nodes = [n for n in nodes if n["id"] not in parent_map and not _is_helper(n)]
    graph_node_ids = {n["id"] for n in graph_nodes}

    dedup: set[tuple[str, str, str]] = set()
    remapped: list[dict] = []
    for e in edges:
        source = parent_map.get(e["source"], e["source"])
        target = parent_map.get(e["target"], e["target"])
        if source == target:
            continue
        k = (source, target, e["edge_type"].value)
        if k in dedup:
            continue
        dedup.add(k)
        remapped.append({"source": source, "target": target, "edge_type": e["edge_type"].value})

    graph_edges = []
    for e in remapped:
        if e["source"] not in graph_node_ids or e["target"] not in graph_node_ids:
            continue
        if e["edge_type"] in ARCH_DROPPED_EDGE_TYPES:
            continue
        if e["edge_type"] == "references":
            if not _should_keep_reference_edge(nodes_by_id.get(e["source"]), nodes_by_id.get(e["target"])):
                continue
        graph_edges.append(e)

    return graph_nodes, graph_edges


def test_phase3_projection_keeps_medium_story_readable() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "medium-step-functions.tfstate"))
    nodes, edges = _project_architecture(ir)
    edge_types = {e["edge_type"] for e in edges}
    assert 9 <= len(nodes) <= 13
    assert len(edges) >= 14
    assert {"triggers", "writes_to", "routes_to"}.issubset(edge_types)


def test_phase3_projection_keeps_non_serverless_context_without_spaghetti() -> None:
    ir = TerraformParser().parse(str(FIXTURES / "complex-multi-vpc.tfstate"))
    nodes, edges = _project_architecture(ir)
    refs = [e for e in edges if e["edge_type"] == "references"]
    assert 20 <= len(nodes) <= 32
    assert 14 <= len(edges) <= 30
    assert len(refs) <= 20


def test_phase3_projection_removes_auth_and_contains_noise() -> None:
    for fixture in ("simple-lambda-api.tfstate", "ecs-alb-service.tfstate", "lambda-vpc-dataflow.tfstate"):
        ir = TerraformParser().parse(str(FIXTURES / fixture))
        _, edges = _project_architecture(ir)
        assert all(e["edge_type"] not in {"authenticates", "contains"} for e in edges)
