"""Suggestion engine: analyze IR and propose grouping rules."""

from __future__ import annotations

import re
from collections import defaultdict

from stackmap.grouping.engine import AutoDetectConfig, GroupingRule, SmartGroupConfig
from stackmap.parsers.base import StackMapIR


# Color palette for suggested groups.
_COLORS = [
    "#ef4444", "#3b82f6", "#22c55e", "#f59e0b",
    "#8b5cf6", "#ec4899", "#06b6d4", "#f97316",
    "#14b8a6", "#a855f7",
]

# Category → icon mapping.
_CATEGORY_ICONS: dict[str, str] = {
    "security": "security",
    "database": "database",
    "compute": "compute",
    "serverless": "serverless",
    "integration": "integration",
    "network": "network",
    "storage": "storage",
}


def suggest_groups(ir: StackMapIR) -> list[SmartGroupConfig]:
    """Analyze IR and suggest grouping rules the user can accept/modify."""
    suggestions: list[SmartGroupConfig] = []
    color_idx = 0

    def _next_color() -> str:
        nonlocal color_idx
        c = _COLORS[color_idx % len(_COLORS)]
        color_idx += 1
        return c

    # Strategy 1: Tag-based suggestions
    for tag_key in ("service", "project", "app", "team", "stack"):
        tag_clusters: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            val = node.tags.get(tag_key)
            if val:
                tag_clusters[val].append(node.id)

        for tag_val, node_ids in sorted(tag_clusters.items(), key=lambda x: -len(x[1])):
            if len(node_ids) >= 3:
                suggestions.append(SmartGroupConfig(
                    name=tag_val.replace("-", " ").replace("_", " ").title(),
                    icon=None,
                    color=_next_color(),
                    rules=[GroupingRule(match_type="tag", key=tag_key, value=tag_val)],
                ))

    # Strategy 2: Naming prefix suggestions
    prefix_clusters: dict[str, list[str]] = defaultdict(list)
    for node in ir.nodes:
        parts = re.split(r"[-_.]", node.name)
        if len(parts) >= 2 and len(parts[0]) >= 2:
            prefix_clusters[parts[0]].append(node.id)

    already_grouped = {n for sg in suggestions for r in sg.rules for n in _nodes_for_rule(ir, r)}

    for prefix, node_ids in sorted(prefix_clusters.items(), key=lambda x: -len(x[1])):
        # Skip if most nodes are already in a tag-based suggestion
        ungrouped = [nid for nid in node_ids if nid not in already_grouped]
        if len(ungrouped) >= 3:
            suggestions.append(SmartGroupConfig(
                name=prefix.replace("-", " ").replace("_", " ").title(),
                icon=None,
                color=_next_color(),
                rules=[GroupingRule(match_type="name", pattern=f"{prefix}-*")],
            ))

    # Strategy 3: VPC-based suggestions
    vpc_clusters: dict[str, list[str]] = defaultdict(list)
    for node in ir.nodes:
        vpc_id = node.properties.get("vpc_id") or node.metadata.get("vpc_id", "")
        if vpc_id:
            vpc_clusters[vpc_id].append(node.id)

    for vpc_id, node_ids in vpc_clusters.items():
        if len(node_ids) >= 3:
            short_id = vpc_id[-8:] if len(vpc_id) > 8 else vpc_id
            suggestions.append(SmartGroupConfig(
                name=f"VPC {short_id}",
                icon="network",
                color=_next_color(),
                rules=[GroupingRule(match_type="vpc", value=vpc_id)],
            ))

    return suggestions


def _nodes_for_rule(ir: StackMapIR, rule: GroupingRule) -> set[str]:
    """Get node IDs matching a single rule (for dedup purposes)."""
    from stackmap.grouping.engine import _matches_rule

    return {n.id for n in ir.nodes if _matches_rule(n, rule)}
