"""Smart grouping engine: apply rules and auto-detect resource clusters."""

from __future__ import annotations

import fnmatch
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from stackmap.parsers.base import EdgeType, StackMapGroup, StackMapIR, StackMapNode


@dataclass
class GroupingRule:
    match_type: str  # "tag", "name", "type", "vpc", "subnet", "resource_type"
    key: str | None = None
    value: str | None = None
    pattern: str | None = None
    values: list[str] | None = None
    ids: list[str] | None = None


@dataclass
class SmartGroupConfig:
    name: str
    icon: str | None = None
    color: str | None = None
    rules: list[GroupingRule] = field(default_factory=list)
    group_type: str = "smart_group"


@dataclass
class AutoDetectConfig:
    enabled: bool = True
    tag_keys: list[str] = field(default_factory=lambda: ["service", "project", "app"])
    naming_prefix: bool = True
    min_group_size: int = 3
    vpc_based: bool = True


def load_grouping_config(config_path: str | Path) -> tuple[list[SmartGroupConfig], AutoDetectConfig]:
    """Load .stackmap/groups.yaml and parse into configs.

    Returns:
        Tuple of (explicit group configs, auto-detect config).
    """
    path = Path(config_path)
    if not path.exists():
        return [], AutoDetectConfig()

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    groups: list[SmartGroupConfig] = []
    for group_data in data.get("groups", []):
        rules: list[GroupingRule] = []
        for rule_data in group_data.get("rules", []):
            rules.append(GroupingRule(
                match_type=rule_data.get("match", ""),
                key=rule_data.get("key"),
                value=rule_data.get("value"),
                pattern=rule_data.get("pattern"),
                values=rule_data.get("values"),
                ids=rule_data.get("ids"),
            ))
        groups.append(SmartGroupConfig(
            name=group_data["name"],
            icon=group_data.get("icon"),
            color=group_data.get("color"),
            rules=rules,
        ))

    auto_detect_data = data.get("auto_detect", {})
    auto_config = AutoDetectConfig(
        enabled=auto_detect_data.get("enabled", True),
    )
    for strategy in auto_detect_data.get("strategies", []):
        if "tag_key" in strategy:
            auto_config.tag_keys.append(strategy["tag_key"])
        if strategy.get("naming_prefix"):
            auto_config.naming_prefix = True
            if "min_group_size" in strategy:
                auto_config.min_group_size = strategy["min_group_size"]
        if strategy.get("vpc_based"):
            auto_config.vpc_based = True

    return groups, auto_config


def _matches_rule(node: StackMapNode, rule: GroupingRule) -> bool:
    """Check if a node matches a single grouping rule."""
    if rule.match_type == "tag":
        if rule.key and rule.value:
            return node.tags.get(rule.key) == rule.value
        if rule.key and rule.values:
            return node.tags.get(rule.key) in rule.values
        return False

    if rule.match_type == "name":
        if rule.pattern:
            return fnmatch.fnmatch(node.name, rule.pattern)
        if rule.value:
            return node.name == rule.value
        return False

    if rule.match_type == "type" or rule.match_type == "resource_type":
        if rule.pattern:
            return fnmatch.fnmatch(node.resource_type, rule.pattern)
        if rule.values:
            return node.resource_type in rule.values
        if rule.value:
            return node.resource_type == rule.value
        return False

    if rule.match_type == "vpc":
        node_vpc = node.properties.get("vpc_id") or node.metadata.get("vpc_id", "")
        if rule.ids:
            return node_vpc in rule.ids
        if rule.value:
            return node_vpc == rule.value
        return False

    if rule.match_type == "subnet":
        node_subnet = node.properties.get("subnet_id") or node.metadata.get("subnet_id", "")
        if rule.ids:
            return node_subnet in rule.ids
        return False

    return False


def apply_smart_groups(ir: StackMapIR, configs: list[SmartGroupConfig]) -> StackMapIR:
    """Apply grouping rules to IR. Returns new IR with added StackMapGroups.

    Each node can belong to at most one smart group (first match wins).
    """
    assigned: set[str] = set()
    new_groups: list[StackMapGroup] = list(ir.groups)

    for config in configs:
        members: list[str] = []
        for node in ir.nodes:
            if node.id in assigned:
                continue
            if any(_matches_rule(node, rule) for rule in config.rules):
                members.append(node.id)
                assigned.add(node.id)

        if members:
            group_id = f"smart_group:{config.name.lower().replace(' ', '_')}"
            new_groups.append(StackMapGroup(
                id=group_id,
                name=config.name,
                group_type="smart_group",
                children=members,
                metadata={
                    "icon": config.icon,
                    "color": config.color,
                    "rule_count": len(config.rules),
                },
            ))

    return StackMapIR(
        metadata=ir.metadata,
        nodes=ir.nodes,
        edges=ir.edges,
        groups=new_groups,
    )


def auto_detect_groups(
    ir: StackMapIR,
    config: AutoDetectConfig | None = None,
) -> list[StackMapGroup]:
    """Heuristic grouping when no explicit rules match.

    Strategies (applied in order):
    1. Tag-based clustering: group by common tag values.
    2. Naming prefix: group by common name prefix.
    3. VPC-based: one group per VPC.
    4. Connectivity-based: connected components.
    """
    if config is None:
        config = AutoDetectConfig()

    groups: list[StackMapGroup] = []
    assigned: set[str] = set()

    # Strategy 1: Tag-based clustering
    for tag_key in config.tag_keys:
        tag_clusters: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            if node.id in assigned:
                continue
            tag_val = node.tags.get(tag_key)
            if tag_val:
                tag_clusters[tag_val].append(node.id)

        for tag_val, node_ids in tag_clusters.items():
            if len(node_ids) >= config.min_group_size:
                group_id = f"auto:{tag_key}:{tag_val.lower().replace(' ', '_')}"
                groups.append(StackMapGroup(
                    id=group_id,
                    name=f"{tag_val}",
                    group_type="smart_group",
                    children=node_ids,
                    metadata={"auto_strategy": "tag", "tag_key": tag_key, "tag_value": tag_val},
                ))
                assigned.update(node_ids)

    # Strategy 2: Naming prefix clustering
    if config.naming_prefix:
        prefix_clusters: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            if node.id in assigned:
                continue
            # Extract prefix (split on -, _, .)
            parts = re.split(r"[-_.]", node.name)
            if len(parts) >= 2:
                prefix = parts[0]
                if len(prefix) >= 2:
                    prefix_clusters[prefix].append(node.id)

        for prefix, node_ids in prefix_clusters.items():
            if len(node_ids) >= config.min_group_size:
                group_id = f"auto:prefix:{prefix.lower()}"
                groups.append(StackMapGroup(
                    id=group_id,
                    name=f"{prefix}",
                    group_type="smart_group",
                    children=node_ids,
                    metadata={"auto_strategy": "naming_prefix", "prefix": prefix},
                ))
                assigned.update(node_ids)

    # Strategy 3: VPC-based clustering
    if config.vpc_based:
        vpc_clusters: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            if node.id in assigned:
                continue
            vpc_id = node.properties.get("vpc_id") or node.metadata.get("vpc_id", "")
            if vpc_id:
                vpc_clusters[vpc_id].append(node.id)

        for vpc_id, node_ids in vpc_clusters.items():
            if len(node_ids) >= 2:
                group_id = f"auto:vpc:{vpc_id}"
                groups.append(StackMapGroup(
                    id=group_id,
                    name=f"VPC {vpc_id[-8:]}",
                    group_type="smart_group",
                    children=node_ids,
                    metadata={"auto_strategy": "vpc", "vpc_id": vpc_id},
                ))
                assigned.update(node_ids)

    # Strategy 4: Connectivity-based clustering (connected components)
    # Build adjacency graph excluding CONTAINS and REFERENCES
    adj: dict[str, set[str]] = defaultdict(set)
    for edge in ir.edges:
        if edge.edge_type in (EdgeType.CONTAINS, EdgeType.REFERENCES):
            continue
        adj[edge.source].add(edge.target)
        adj[edge.target].add(edge.source)

    unassigned = {n.id for n in ir.nodes} - assigned
    visited: set[str] = set()

    for start in unassigned:
        if start in visited:
            continue
        # BFS to find connected component
        component: list[str] = []
        queue = [start]
        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            if node_id in unassigned:
                component.append(node_id)
            for neighbor in adj.get(node_id, set()):
                if neighbor not in visited and neighbor in unassigned:
                    queue.append(neighbor)

        if len(component) >= config.min_group_size:
            group_id = f"auto:component:{component[0]}"
            groups.append(StackMapGroup(
                id=group_id,
                name=f"Component ({len(component)} resources)",
                group_type="smart_group",
                children=component,
                metadata={"auto_strategy": "connectivity"},
            ))

    return groups
