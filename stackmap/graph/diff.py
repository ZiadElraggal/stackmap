"""Diff engine: compare two StackMapIR snapshots and produce a StackMapDiff."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from stackmap.parsers.base import EdgeType, StackMapEdge, StackMapIR, StackMapNode


# Per-resource-type properties compared for "modified" detection.
# For types not in this map, all non-volatile properties are compared.
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
    "aws_eks_cluster": {"version"},
    "aws_ecr_repository": {"image_tag_mutability"},
}

# Properties to always ignore in comparison regardless of resource type
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
    status: str  # "added" | "removed" | "modified" | "unchanged"
    node: StackMapNode  # "to" for added/modified/unchanged, "from" for removed
    changes: dict | None = None  # For modified: { property: { old: X, new: Y } }


@dataclass
class EdgeDiff:
    edge_id: str
    status: str  # "added" | "removed" | "unchanged"
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
            "node_diffs": [_node_diff_to_dict(nd) for nd in self.node_diffs],
            "edge_diffs": [_edge_diff_to_dict(ed) for ed in self.edge_diffs],
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
        """
        Produce a StackMapIR that encodes diff status for frontend rendering.

        Each node gets ``diff_status`` (and optionally ``diff_changes``) injected
        into its ``position_hint``.  Edge diff statuses are stored in
        ``metadata["edge_diff_status"]`` keyed by edge ID.  Removed nodes are
        included so the time-travel slider can fade them in/out.
        """
        annotated_nodes: list[StackMapNode] = []
        for nd in self.node_diffs:
            n = nd.node
            annotated_nodes.append(
                StackMapNode(
                    id=n.id,
                    name=n.name,
                    resource_type=n.resource_type,
                    provider=n.provider,
                    category=n.category,
                    properties=n.properties,
                    tags=n.tags,
                    position_hint={
                        **n.position_hint,
                        "diff_status": nd.status,
                        "diff_changes": nd.changes or {},
                    },
                )
            )

        edge_diff_status: dict[str, str] = {}
        annotated_edges: list[StackMapEdge] = []
        for ed in self.edge_diffs:
            edge_diff_status[ed.edge.id] = ed.status
            annotated_edges.append(ed.edge)

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
    """Return a dict of changed properties, or None if the nodes are identical."""
    rtype = node_to.resource_type
    keys: set[str] | None = DIFF_PROPERTIES.get(rtype)

    props_from = node_from.properties
    props_to = node_to.properties

    if keys is None:
        keys = (set(props_from.keys()) | set(props_to.keys())) - _IGNORE_PROPERTIES

    changes: dict = {}
    for key in keys:
        val_from = props_from.get(key)
        val_to = props_to.get(key)
        if val_from != val_to:
            changes[key] = {"old": val_from, "new": val_to}

    return changes if changes else None


def compute_diff(from_ir: StackMapIR, to_ir: StackMapIR) -> StackMapDiff:
    """Compute a diff between two StackMapIR snapshots."""
    from_nodes: dict[str, StackMapNode] = {n.id: n for n in from_ir.nodes}
    to_nodes: dict[str, StackMapNode] = {n.id: n for n in to_ir.nodes}
    from_edges: dict[str, StackMapEdge] = {e.id: e for e in from_ir.edges}
    to_edges: dict[str, StackMapEdge] = {e.id: e for e in to_ir.edges}

    all_node_ids = set(from_nodes) | set(to_nodes)
    all_edge_ids = set(from_edges) | set(to_edges)

    node_diffs: list[NodeDiff] = []
    summary = DiffSummary()

    for nid in all_node_ids:
        in_from = nid in from_nodes
        in_to = nid in to_nodes

        if in_to and not in_from:
            node_diffs.append(NodeDiff(node_id=nid, status="added", node=to_nodes[nid]))
            summary.added += 1
        elif in_from and not in_to:
            node_diffs.append(NodeDiff(node_id=nid, status="removed", node=from_nodes[nid]))
            summary.removed += 1
        else:
            changes = _compare_properties(from_nodes[nid], to_nodes[nid])
            if changes:
                node_diffs.append(
                    NodeDiff(
                        node_id=nid,
                        status="modified",
                        node=to_nodes[nid],
                        changes=changes,
                    )
                )
                summary.modified += 1
            else:
                node_diffs.append(
                    NodeDiff(node_id=nid, status="unchanged", node=to_nodes[nid])
                )
                summary.unchanged += 1

    edge_diffs: list[EdgeDiff] = []
    for eid in all_edge_ids:
        in_from = eid in from_edges
        in_to = eid in to_edges

        if in_to and not in_from:
            edge_diffs.append(EdgeDiff(edge_id=eid, status="added", edge=to_edges[eid]))
        elif in_from and not in_to:
            edge_diffs.append(EdgeDiff(edge_id=eid, status="removed", edge=from_edges[eid]))
        else:
            edge_diffs.append(EdgeDiff(edge_id=eid, status="unchanged", edge=to_edges[eid]))

    return StackMapDiff(
        from_metadata=from_ir.metadata,
        to_metadata=to_ir.metadata,
        node_diffs=node_diffs,
        edge_diffs=edge_diffs,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _node_diff_to_dict(nd: NodeDiff) -> dict:
    from stackmap.parsers.base import _node_to_dict  # noqa: PLC0415

    return {
        "node_id": nd.node_id,
        "status": nd.status,
        "node": _node_to_dict(nd.node),
        "changes": nd.changes,
    }


def _edge_diff_to_dict(ed: EdgeDiff) -> dict:
    from stackmap.parsers.base import _edge_to_dict  # noqa: PLC0415

    return {
        "edge_id": ed.edge_id,
        "status": ed.status,
        "edge": _edge_to_dict(ed.edge),
    }
