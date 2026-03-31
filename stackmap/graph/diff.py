"""Diff engine: compare two StackMapIR snapshots and produce a StackMapDiff."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from stackmap.parsers.base import StackMapEdge, StackMapIR, StackMapNode


DIFF_PROPERTIES: dict[str, set[str]] = {
    "aws_lambda_function": {"runtime", "memory_size", "timeout", "handler", "environment"},
    "aws_dynamodb_table": {"billing_mode", "hash_key", "range_key", "global_secondary_indexes"},
    "aws_s3_bucket": {"acl", "versioning"},
    "aws_db_instance": {"instance_class", "engine", "engine_version", "storage_type", "multi_az"},
    "aws_ecs_service": {"desired_count", "task_definition"},
    "aws_ecs_task_definition": {"family", "cpu", "memory", "network_mode"},
    "aws_sqs_queue": {"fifo_queue", "visibility_timeout_seconds", "delay_seconds"},
    "aws_sns_topic": {"fifo_topic"},
    "aws_api_gateway_rest_api": {"name", "description"},
    "aws_cloudfront_distribution": {"enabled", "default_cache_behavior"},
    "aws_elasticache_replication_group": {"node_type", "num_node_groups", "num_cache_clusters"},
    "aws_ecr_repository": {"image_tag_mutability"},
}

_IGNORE_PROPERTIES = frozenset(
    {
        "last_modified",
        "arn",
        "created_at",
        "updated_at",
        "id",
        "tags_all",
        "timeouts",
    }
)


@dataclass
class NodeDiff:
    node_id: str
    status: str
    node: StackMapNode
    changes: dict | None = None


@dataclass
class EdgeDiff:
    edge_id: str
    status: str
    edge: StackMapEdge


@dataclass
class DiffSummary:
    added: int = 0
    removed: int = 0
    modified: int = 0
    unchanged: int = 0


@dataclass
class StackMapDiff:
    from_metadata: dict = field(default_factory=dict)
    to_metadata: dict = field(default_factory=dict)
    node_diffs: list[NodeDiff] = field(default_factory=list)
    edge_diffs: list[EdgeDiff] = field(default_factory=list)
    summary: DiffSummary = field(default_factory=DiffSummary)

    def to_dict(self) -> dict:
        return {
            "from_metadata": self.from_metadata,
            "to_metadata": self.to_metadata,
            "node_diffs": [_node_diff_to_dict(diff) for diff in self.node_diffs],
            "edge_diffs": [_edge_diff_to_dict(diff) for diff in self.edge_diffs],
            "summary": {
                "added": self.summary.added,
                "removed": self.summary.removed,
                "modified": self.summary.modified,
                "unchanged": self.summary.unchanged,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json())

    def to_diff_ir(self) -> StackMapIR:
        annotated_nodes: list[StackMapNode] = []
        for diff in self.node_diffs:
            node = diff.node
            annotated_nodes.append(
                StackMapNode(
                    id=node.id,
                    name=node.name,
                    resource_type=node.resource_type,
                    provider=node.provider,
                    category=node.category,
                    properties=node.properties,
                    tags=node.tags,
                    position_hint={
                        **node.position_hint,
                        "diff_status": diff.status,
                        "diff_changes": diff.changes or {},
                    },
                )
            )

        edge_diff_status: dict[str, str] = {}
        annotated_edges: list[StackMapEdge] = []
        for diff in self.edge_diffs:
            edge_diff_status[diff.edge.id] = diff.status
            annotated_edges.append(diff.edge)

        metadata = {
            **self.to_metadata,
            "diff_mode": True,
            "diff_summary": {
                "added": self.summary.added,
                "removed": self.summary.removed,
                "modified": self.summary.modified,
                "unchanged": self.summary.unchanged,
            },
            "diff_from_scanned_at": self.from_metadata.get("scanned_at", ""),
            "diff_to_scanned_at": self.to_metadata.get("scanned_at", ""),
            "edge_diff_status": edge_diff_status,
        }

        return StackMapIR(metadata=metadata, nodes=annotated_nodes, edges=annotated_edges)


def _compare_properties(node_from: StackMapNode, node_to: StackMapNode) -> dict | None:
    resource_type = node_to.resource_type
    keys = DIFF_PROPERTIES.get(resource_type)
    props_from = node_from.properties
    props_to = node_to.properties

    if keys is None:
        keys = (set(props_from.keys()) | set(props_to.keys())) - _IGNORE_PROPERTIES

    changes: dict = {}
    for key in keys:
        if props_from.get(key) != props_to.get(key):
            changes[key] = {
                "old": props_from.get(key),
                "new": props_to.get(key),
            }

    return changes if changes else None


def compute_diff(from_ir: StackMapIR, to_ir: StackMapIR) -> StackMapDiff:
    from_nodes = {node.id: node for node in from_ir.nodes}
    to_nodes = {node.id: node for node in to_ir.nodes}
    from_edges = {edge.id: edge for edge in from_ir.edges}
    to_edges = {edge.id: edge for edge in to_ir.edges}

    node_diffs: list[NodeDiff] = []
    summary = DiffSummary()

    for node_id in set(from_nodes) | set(to_nodes):
        in_from = node_id in from_nodes
        in_to = node_id in to_nodes

        if in_to and not in_from:
            node_diffs.append(NodeDiff(node_id=node_id, status="added", node=to_nodes[node_id]))
            summary.added += 1
            continue
        if in_from and not in_to:
            node_diffs.append(NodeDiff(node_id=node_id, status="removed", node=from_nodes[node_id]))
            summary.removed += 1
            continue

        changes = _compare_properties(from_nodes[node_id], to_nodes[node_id])
        if changes:
            node_diffs.append(
                NodeDiff(node_id=node_id, status="modified", node=to_nodes[node_id], changes=changes)
            )
            summary.modified += 1
        else:
            node_diffs.append(NodeDiff(node_id=node_id, status="unchanged", node=to_nodes[node_id]))
            summary.unchanged += 1

    edge_diffs: list[EdgeDiff] = []
    for edge_id in set(from_edges) | set(to_edges):
        in_from = edge_id in from_edges
        in_to = edge_id in to_edges
        if in_to and not in_from:
            edge_diffs.append(EdgeDiff(edge_id=edge_id, status="added", edge=to_edges[edge_id]))
        elif in_from and not in_to:
            edge_diffs.append(EdgeDiff(edge_id=edge_id, status="removed", edge=from_edges[edge_id]))
        else:
            edge_diffs.append(EdgeDiff(edge_id=edge_id, status="unchanged", edge=to_edges[edge_id]))

    return StackMapDiff(
        from_metadata=from_ir.metadata,
        to_metadata=to_ir.metadata,
        node_diffs=node_diffs,
        edge_diffs=edge_diffs,
        summary=summary,
    )


def _node_diff_to_dict(diff: NodeDiff) -> dict:
    from stackmap.parsers.base import _node_to_dict

    return {
        "node_id": diff.node_id,
        "status": diff.status,
        "node": _node_to_dict(diff.node),
        "changes": diff.changes,
    }


def _edge_diff_to_dict(diff: EdgeDiff) -> dict:
    from stackmap.parsers.base import _edge_to_dict

    return {
        "edge_id": diff.edge_id,
        "status": diff.status,
        "edge": _edge_to_dict(diff.edge),
    }
