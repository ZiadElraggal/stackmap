"""Dependency tracing: upstream/downstream traversal and blast radius analysis."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from stackmap.parsers.base import EdgeType, StackMapEdge, StackMapIR, StackMapNode


# Edge types that represent structural containment, not functional dependency.
_STRUCTURAL_EDGE_TYPES = frozenset({EdgeType.CONTAINS})

# For "upstream" direction we follow edges backward.
# The semantics: if A triggers B, then A is upstream of B.
# If A reads_from B, then B is upstream data dependency of A.
_UPSTREAM_SEMANTICS: dict[EdgeType, str] = {
    EdgeType.TRIGGERS: "reverse",       # A triggers B → follow B→A for upstream of B
    EdgeType.READS_FROM: "forward",     # A reads_from B → B is upstream of A, so follow A→B
    EdgeType.WRITES_TO: "reverse",      # A writes_to B → A is upstream of B
    EdgeType.ROUTES_TO: "reverse",      # A routes_to B → A is upstream of B
    EdgeType.AUTHENTICATES: "forward",  # A authenticates_with B → B is upstream auth dep of A
    EdgeType.DEPENDS_ON: "reverse",     # A depends_on B → B is upstream of A
    EdgeType.REFERENCES: "reverse",     # weak link
    EdgeType.CROSS_ACCOUNT_REFERENCE: "reverse",
}


@dataclass
class TraceHop:
    """A single hop in the dependency trace."""

    node_id: str
    depth: int
    edge_type: str
    edge_label: str
    direction: str  # "upstream" | "downstream"

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "depth": self.depth,
            "edge_type": self.edge_type,
            "edge_label": self.edge_label,
            "direction": self.direction,
        }


@dataclass
class TraceResult:
    """Full trace result from a single origin node."""

    origin_id: str
    upstream: list[TraceHop] = field(default_factory=list)
    downstream: list[TraceHop] = field(default_factory=list)
    blast_radius: int = 0
    critical_path: list[str] = field(default_factory=list)
    critical_path_length: int = 0

    def to_dict(self) -> dict:
        return {
            "origin_id": self.origin_id,
            "upstream": [h.to_dict() for h in self.upstream],
            "downstream": [h.to_dict() for h in self.downstream],
            "blast_radius": self.blast_radius,
            "critical_path": self.critical_path,
            "critical_path_length": self.critical_path_length,
        }


def _build_adjacency(
    edges: list[StackMapEdge],
    exclude_edge_types: frozenset[EdgeType] | None = None,
) -> tuple[dict[str, list[tuple[str, StackMapEdge]]], dict[str, list[tuple[str, StackMapEdge]]]]:
    """Build forward and reverse adjacency lists from edges.

    Returns (forward_adj, reverse_adj) where:
    - forward_adj[source] = [(target, edge), ...]
    - reverse_adj[target] = [(source, edge), ...]
    """
    exclude = exclude_edge_types or _STRUCTURAL_EDGE_TYPES
    forward: dict[str, list[tuple[str, StackMapEdge]]] = {}
    reverse: dict[str, list[tuple[str, StackMapEdge]]] = {}

    for edge in edges:
        if edge.edge_type in exclude:
            continue
        forward.setdefault(edge.source, []).append((edge.target, edge))
        reverse.setdefault(edge.target, []).append((edge.source, edge))

    return forward, reverse


def _bfs_trace(
    start: str,
    adj: dict[str, list[tuple[str, StackMapEdge]]],
    direction: str,
    max_depth: int,
    include_edge_types: set[EdgeType] | None = None,
    weak_max_depth: int = 1,
) -> list[TraceHop]:
    """BFS traversal producing TraceHop entries.

    weak_max_depth limits how deep REFERENCES edges are followed (default: 1).
    """
    visited: set[str] = {start}
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    hops: list[TraceHop] = []

    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        neighbors = adj.get(node_id, [])
        for neighbor_id, edge in neighbors:
            if neighbor_id in visited:
                continue
            if include_edge_types and edge.edge_type not in include_edge_types:
                continue
            # Weak links (REFERENCES) only followed to limited depth
            if edge.edge_type == EdgeType.REFERENCES and depth + 1 > weak_max_depth:
                continue

            visited.add(neighbor_id)
            hop = TraceHop(
                node_id=neighbor_id,
                depth=depth + 1,
                edge_type=edge.edge_type.value,
                edge_label=edge.label,
                direction=direction,
            )
            hops.append(hop)
            queue.append((neighbor_id, depth + 1))

    return hops


def _find_critical_path(
    origin_id: str,
    downstream_hops: list[TraceHop],
    forward_adj: dict[str, list[tuple[str, StackMapEdge]]],
) -> list[str]:
    """Find the longest downstream path from origin using DFS."""
    if not downstream_hops:
        return [origin_id]

    downstream_ids = {h.node_id for h in downstream_hops}
    downstream_ids.add(origin_id)

    # Build sub-adjacency within downstream set
    sub_adj: dict[str, list[str]] = {}
    for node_id in downstream_ids:
        sub_adj[node_id] = []
        for neighbor_id, edge in forward_adj.get(node_id, []):
            if neighbor_id in downstream_ids and edge.edge_type != EdgeType.CONTAINS:
                sub_adj[node_id].append(neighbor_id)

    # DFS longest path from origin
    best_path: list[str] = [origin_id]

    def _dfs(current: str, path: list[str], visited: set[str]) -> None:
        nonlocal best_path
        if len(path) > len(best_path):
            best_path = list(path)
        for neighbor in sub_adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                path.append(neighbor)
                _dfs(neighbor, path, visited)
                path.pop()
                visited.discard(neighbor)

    _dfs(origin_id, [origin_id], {origin_id})
    return best_path


def trace_dependencies(
    ir: StackMapIR,
    origin_id: str,
    max_depth: int = 10,
    direction: str = "both",
    include_edge_types: set[EdgeType] | None = None,
    exclude_edge_types: frozenset[EdgeType] | None = None,
) -> TraceResult:
    """Trace upstream dependencies and downstream impact from an origin node.

    Args:
        ir: The infrastructure IR to trace through.
        origin_id: Node ID to trace from.
        max_depth: Maximum traversal depth.
        direction: "upstream", "downstream", or "both".
        include_edge_types: If set, only follow these edge types.
        exclude_edge_types: Edge types to skip (defaults to CONTAINS).

    Returns:
        TraceResult with upstream hops, downstream hops, blast radius,
        and critical path.

    Raises:
        ValueError: If origin_id is not found in the IR.
    """
    node_ids = {n.id for n in ir.nodes}
    if origin_id not in node_ids:
        raise ValueError(f"Origin node not found: {origin_id}")

    exclude = exclude_edge_types or _STRUCTURAL_EDGE_TYPES
    forward_adj, reverse_adj = _build_adjacency(ir.edges, exclude)

    upstream: list[TraceHop] = []
    downstream: list[TraceHop] = []

    if direction in ("upstream", "both"):
        upstream = _bfs_trace(
            origin_id, reverse_adj, "upstream", max_depth, include_edge_types
        )

    if direction in ("downstream", "both"):
        downstream = _bfs_trace(
            origin_id, forward_adj, "downstream", max_depth, include_edge_types
        )

    blast_radius = len({h.node_id for h in downstream})
    critical_path = _find_critical_path(origin_id, downstream, forward_adj)

    return TraceResult(
        origin_id=origin_id,
        upstream=upstream,
        downstream=downstream,
        blast_radius=blast_radius,
        critical_path=critical_path,
        critical_path_length=len(critical_path) - 1,
    )


def find_node_by_name(ir: StackMapIR, name_or_id: str) -> StackMapNode | None:
    """Find a node by ID or name (case-insensitive partial match on name)."""
    # Exact ID match first
    for node in ir.nodes:
        if node.id == name_or_id:
            return node
    # Exact name match
    for node in ir.nodes:
        if node.name == name_or_id:
            return node
    # Case-insensitive partial name match
    lower = name_or_id.lower()
    for node in ir.nodes:
        if lower in node.name.lower():
            return node
    return None
