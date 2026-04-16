"""Deterministic natural-language graph query fallback."""

from __future__ import annotations

from stackmap.parsers.base import StackMapIR


def query_ir(ir: StackMapIR, query: str) -> dict:
    """Translate a small natural-language query into node/edge filters.

    This intentionally runs locally. If an external model provider is configured
    later, the endpoint can delegate to it and keep this as the no-key fallback.
    """
    q = query.strip().lower()
    node_ids: set[str] = set()
    edge_ids: set[str] = set()

    def add_matching_nodes(predicate) -> None:
        for node in ir.nodes:
            if predicate(node):
                node_ids.add(node.id)

    if not q:
        return {"filter": {"nodeIds": [], "edgeIds": []}, "reason": "Empty query."}

    if "public" in q or "internet" in q:
        add_matching_nodes(
            lambda node: (
                node.properties.get("publicly_accessible") is True
                or node.properties.get("acl") in {"public-read", "public-read-write"}
                or "0.0.0.0/0" in str(node.properties)
                or "::/0" in str(node.properties)
            )
        )
    elif "cost" in q or "expensive" in q:
        estimates = [
            (node.position_hint.get("cost_monthly", 0), node.id)
            for node in ir.nodes
            if isinstance(node.position_hint.get("cost_monthly"), (int, float))
        ]
        for _, node_id in sorted(estimates, reverse=True)[:10]:
            node_ids.add(node_id)
    elif "database" in q or "db" in q:
        add_matching_nodes(lambda node: node.category.value == "database" or "db" in node.resource_type)
    elif "lambda" in q or "function" in q:
        add_matching_nodes(lambda node: "lambda" in node.resource_type.lower() or "function" in node.resource_type.lower())
    elif "depends on" in q or "depend on" in q:
        needle = q.split("depends on", 1)[-1].strip() if "depends on" in q else q.split("depend on", 1)[-1].strip()
        matches = [node for node in ir.nodes if needle and (needle in node.name.lower() or needle in node.id.lower())]
        targets = {node.id for node in matches}
        for edge in ir.edges:
            if edge.target in targets:
                node_ids.add(edge.source)
                node_ids.add(edge.target)
                edge_ids.add(edge.id)
    else:
        add_matching_nodes(
            lambda node: q in node.name.lower()
            or q in node.id.lower()
            or q in node.resource_type.lower()
            or q in node.category.value
        )

    if not edge_ids and node_ids:
        for edge in ir.edges:
            if edge.source in node_ids and edge.target in node_ids:
                edge_ids.add(edge.id)

    return {
        "filter": {"nodeIds": sorted(node_ids), "edgeIds": sorted(edge_ids)},
        "reason": f"Matched {len(node_ids)} resources and {len(edge_ids)} relationships locally.",
    }
