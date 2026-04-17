"""Suggestion engine: analyze IR and propose grouping rules."""

from __future__ import annotations

import re
from collections import defaultdict

from stackmap.grouping.engine import GroupingRule, SmartGroupConfig
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
    suggested_keys: set[tuple[str, str, str]] = set()

    def _next_color() -> str:
        nonlocal color_idx
        c = _COLORS[color_idx % len(_COLORS)]
        color_idx += 1
        return c

    def _append_tag_suggestions(
        tag_key: str,
        *,
        signal: str,
        icon: str | None = None,
        min_size: int = 3,
    ) -> None:
        tag_clusters: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            val = node.tags.get(tag_key)
            if val:
                tag_clusters[val].append(node.id)

        for tag_val, node_ids in sorted(tag_clusters.items(), key=lambda x: -len(x[1])):
            dedup_key = ("tag", tag_key, tag_val)
            if len(node_ids) >= min_size and dedup_key not in suggested_keys:
                suggested_keys.add(dedup_key)
                suggestions.append(SmartGroupConfig(
                    name=tag_val.replace("-", " ").replace("_", " ").title(),
                    icon=icon,
                    color=_next_color(),
                    rules=[GroupingRule(match_type="tag", key=tag_key, value=tag_val)],
                    metadata={
                        "confidence": _confidence(len(node_ids), len(ir.nodes), base=0.72 if signal in {"service", "environment"} else 0.64),
                        "signals": [signal, f"tag:{tag_key}"],
                        "comment": f"confidence: {_confidence(len(node_ids), len(ir.nodes), base=0.72 if signal in {'service', 'environment'} else 0.64):.2f}",
                    },
                ))

    # Strategy 1: Tag-based suggestions. Business/service tags are emitted
    # first, then environment/team scopes for humans who want hierarchy.
    for tag_key in ("service", "project", "app", "component", "workload"):
        _append_tag_suggestions(tag_key, signal="service")
    for tag_key in ("env", "environment", "stage", "tier"):
        _append_tag_suggestions(tag_key, signal="environment")
    for tag_key in ("team", "owner", "squad", "department"):
        _append_tag_suggestions(tag_key, signal="team")
    _append_tag_suggestions("stack", signal="stack")

    # Strategy 2: Terraform module path suggestions.
    module_clusters: dict[str, list[str]] = defaultdict(list)
    for node in ir.nodes:
        module = (
            node.metadata.get("source_module")
            or node.metadata.get("module")
            or node.properties.get("source_module")
            or ""
        )
        if module:
            module_clusters[str(module)].append(node.id)

    for module, node_ids in sorted(module_clusters.items(), key=lambda x: -len(x[1])):
        if len(node_ids) >= 3:
            short = module.split(".")[-1].replace("_", " ").replace("-", " ").title()
            suggestions.append(SmartGroupConfig(
                name=short,
                icon=None,
                color=_next_color(),
                rules=[GroupingRule(match_type="metadata", key="source_module", value=module)],
                metadata={
                    "confidence": _confidence(len(node_ids), len(ir.nodes), base=0.62),
                    "signals": ["module_path", module],
                    "comment": f"confidence: {_confidence(len(node_ids), len(ir.nodes), base=0.62):.2f}",
                    "module": module,
                },
            ))

    # Strategy 3: Naming prefix suggestions
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
                metadata={
                    "confidence": _confidence(len(ungrouped), len(ir.nodes), base=0.52),
                    "signals": ["naming_prefix"],
                    "comment": f"confidence: {_confidence(len(ungrouped), len(ir.nodes), base=0.52):.2f}",
                },
            ))

    # Strategy 4: VPC-based suggestions
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
                metadata={
                    "confidence": _confidence(len(node_ids), len(ir.nodes), base=0.46),
                    "signals": ["vpc"],
                    "comment": f"confidence: {_confidence(len(node_ids), len(ir.nodes), base=0.46):.2f}",
                },
            ))

    return suggestions


def _confidence(cluster_size: int, total_size: int, *, base: float) -> float:
    if total_size <= 0:
        return round(base, 2)
    coverage = min(cluster_size / max(total_size, 1), 1.0)
    return round(min(0.95, base + 0.2 * coverage), 2)


def _nodes_for_rule(ir: StackMapIR, rule: GroupingRule) -> set[str]:
    """Get node IDs matching a single rule (for dedup purposes)."""
    from stackmap.grouping.engine import _matches_rule

    return {n.id for n in ir.nodes if _matches_rule(n, rule)}
