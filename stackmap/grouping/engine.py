"""Smart grouping engine for explicit rules and UI-first auto-clustering.

Auto-detected groups are intentionally heuristic rather than authoritative.
The serve flow uses them to make large graphs readable without requiring
users to hand-author grouping config first.

Detection order matters:
1. Tag clusters (`service`, `project`, `app` by default)
2. Name-prefix clusters (`api-*`, `payments_*`, etc.)
3. VPC clusters
4. Connectivity clusters

Earlier strategies claim nodes first, which keeps groups easier to explain in
the UI: business/service tags win over structural fallbacks like VPCs.
"""

from __future__ import annotations

import fnmatch
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from stackmap.parsers.base import EdgeType, StackMapGroup, StackMapIR, StackMapNode


@dataclass
class GroupingRule:
    match_type: str  # "tag", "name", "type", "vpc", "subnet", "resource_type", "metadata"
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
    metadata: dict = field(default_factory=dict)


@dataclass
class AutoDetectConfig:
    enabled: bool = True
    tag_keys: list[str] = field(default_factory=lambda: [
        "service", "project", "app", "component", "workload",
    ])
    env_tag_keys: list[str] = field(default_factory=lambda: [
        "env", "environment", "stage", "tier",
    ])
    team_tag_keys: list[str] = field(default_factory=lambda: [
        "team", "owner", "squad", "department",
    ])
    naming_prefix: bool = True
    min_group_size: int = 3
    min_prefix_len: int = 2
    vpc_based: bool = True
    subnet_based: bool = False
    region_based: bool = True
    account_based: bool = True
    module_path_based: bool = True
    shared_role_based: bool = True
    hierarchy: bool = True
    confidence_floor: float = 0.35


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
            metadata=group_data.get("metadata") or {},
        ))

    auto_detect_data = data.get("auto_detect", {})
    auto_config = AutoDetectConfig(
        enabled=auto_detect_data.get("enabled", True),
    )
    # v2 flat keys (preferred).
    for key in (
        "naming_prefix", "min_group_size", "min_prefix_len", "vpc_based",
        "subnet_based", "region_based", "account_based", "module_path_based",
        "shared_role_based", "hierarchy", "confidence_floor",
    ):
        if key in auto_detect_data:
            setattr(auto_config, key, auto_detect_data[key])
    if "tag_keys" in auto_detect_data and isinstance(auto_detect_data["tag_keys"], list):
        auto_config.tag_keys = list(auto_detect_data["tag_keys"])
    if "env_tag_keys" in auto_detect_data and isinstance(auto_detect_data["env_tag_keys"], list):
        auto_config.env_tag_keys = list(auto_detect_data["env_tag_keys"])
    if "team_tag_keys" in auto_detect_data and isinstance(auto_detect_data["team_tag_keys"], list):
        auto_config.team_tag_keys = list(auto_detect_data["team_tag_keys"])
    # Back-compat: older ``strategies`` list still supported.
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

    if rule.match_type == "metadata":
        if not rule.key:
            return False
        node_value = node.metadata.get(rule.key) or node.properties.get(rule.key)
        if rule.values:
            return node_value in rule.values
        if rule.value:
            return node_value == rule.value
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
                    "auto_strategy": "explicit",
                },
            ))

    # Annotate explicit groups with confidence=1.0 and a reason derived
    # from their rule count so the frontend can treat them uniformly.
    nodes_by_id = {n.id: n for n in ir.nodes}
    adj = _build_any_adjacency(ir)
    for group in new_groups:
        if group.group_type != "smart_group":
            continue
        if "confidence" in group.metadata:
            continue
        _annotate_group(group, ir, nodes_by_id, adj)
        # Explicit rules carry maximum confidence regardless of topology.
        if group.metadata.get("auto_strategy") == "explicit":
            group.metadata["confidence"] = 1.0
            group.metadata["reason"] = (
                f"Matches explicit rule{'s' if group.metadata.get('rule_count', 1) != 1 else ''} "
                f"({group.metadata.get('rule_count', 0)})."
            )

    return StackMapIR(
        metadata=ir.metadata,
        nodes=ir.nodes,
        edges=ir.edges,
        groups=new_groups,
        timeline=ir.timeline,
        organization=ir.organization,
        aggregates=ir.aggregates,
    )


def auto_detect_groups(
    ir: StackMapIR,
    config: AutoDetectConfig | None = None,
) -> list[StackMapGroup]:
    """Heuristic grouping when no explicit rules match.

    Strategies run in this order; earlier strategies claim nodes first so
    business/service signals win over structural fallbacks:

    1. Environment tags (``env``, ``stage``, ``tier``) — parent candidates
    2. Service / workload tags (``service``, ``project``, ``app`` …)
    3. Team / owner tags
    4. Terraform module path (``metadata.source_module`` or
       ``position_hint.source_module``)
    5. CloudFormation stack / SAM app (``metadata.stack_name``)
    6. Shared IAM role co-assumers
    7. Naming prefix
    8. VPC
    9. Subnet (opt-in)
    10. Region (only when the IR spans multiple regions)
    11. Account (only for org scans)
    12. Connectivity fallback

    Every returned group carries ``metadata.auto_strategy`` plus
    ``confidence``, ``reason``, ``signals``, ``dominant_categories``.
    Hierarchy is applied at the end when ``config.hierarchy`` is set.
    """
    if config is None:
        config = AutoDetectConfig()

    groups: list[StackMapGroup] = []
    assigned: set[str] = set()
    # Track which strategy owns each node so that later, lower-priority
    # strategies can still *parent* earlier groups without re-assigning.
    strategy_by_node: dict[str, str] = {}
    nodes_by_id = {n.id: n for n in ir.nodes}

    def claim(node_ids: Iterable[str], strategy: str) -> None:
        for nid in node_ids:
            assigned.add(nid)
            strategy_by_node.setdefault(nid, strategy)

    # Strategy 1: Environment tags — parent-tier, does NOT claim nodes so
    # the service/team strategies below can also form groups.
    for tag_key in config.env_tag_keys:
        # Walk full node set, not just unassigned.
        clusters: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            val = node.tags.get(tag_key)
            if val:
                clusters[val].append(node.id)
        for value, node_ids in clusters.items():
            if len(node_ids) >= max(2, config.min_group_size - 1):
                groups.append(_mk_tag_group(
                    strategy="environment", tag_key=tag_key, tag_value=value,
                    node_ids=node_ids, name_prefix="",
                ))

    # Strategy 2: Service / workload tags.
    for tag_key in config.tag_keys:
        for value, node_ids in _cluster_by_tag(ir.nodes, tag_key, assigned).items():
            if len(node_ids) >= config.min_group_size:
                groups.append(_mk_tag_group(
                    strategy="tag", tag_key=tag_key, tag_value=value,
                    node_ids=node_ids, name_prefix="",
                ))
                claim(node_ids, "tag")

    # Strategy 3: Team tags.
    for tag_key in config.team_tag_keys:
        for value, node_ids in _cluster_by_tag(ir.nodes, tag_key, assigned).items():
            if len(node_ids) >= config.min_group_size:
                groups.append(_mk_tag_group(
                    strategy="team", tag_key=tag_key, tag_value=value,
                    node_ids=node_ids, name_prefix="Team ",
                ))
                claim(node_ids, "team")

    # Strategy 4: Terraform module path.
    if config.module_path_based:
        module_clusters: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            if node.id in assigned:
                continue
            module = (
                node.metadata.get("source_module")
                or node.position_hint.get("source_module")
                or ""
            )
            if module and module != "root":
                module_clusters[module].append(node.id)
        for module, node_ids in module_clusters.items():
            if len(node_ids) >= config.min_group_size:
                groups.append(StackMapGroup(
                    id=f"auto:module:{_slug(module)}",
                    name=module.split(".")[-1].replace("_", " ").title() or module,
                    group_type="smart_group",
                    children=node_ids,
                    metadata={
                        "auto_strategy": "module_path",
                        "module": module,
                    },
                ))
                claim(node_ids, "module_path")

    # Strategy 5: CloudFormation stack / SAM app.
    stack_clusters: dict[str, list[str]] = defaultdict(list)
    for node in ir.nodes:
        if node.id in assigned:
            continue
        stack = node.metadata.get("stack_name") or node.metadata.get("stack_id") or ""
        if stack:
            stack_clusters[stack].append(node.id)
    for stack, node_ids in stack_clusters.items():
        if len(node_ids) >= config.min_group_size:
            groups.append(StackMapGroup(
                id=f"auto:stack:{_slug(stack)}",
                name=stack,
                group_type="smart_group",
                children=node_ids,
                metadata={"auto_strategy": "stack", "stack_name": stack},
            ))
            claim(node_ids, "stack")

    # Strategy 6: Shared IAM role.
    if config.shared_role_based:
        role_clusters: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            if node.id in assigned:
                continue
            role = (
                node.properties.get("role_arn")
                or node.properties.get("role")
                or ""
            )
            if role:
                role_clusters[role].append(node.id)
        for role, node_ids in role_clusters.items():
            if len(node_ids) >= 2:
                short = role.rsplit("/", 1)[-1] or role
                groups.append(StackMapGroup(
                    id=f"auto:role:{_slug(short)}",
                    name=f"Role: {short}",
                    group_type="smart_group",
                    children=node_ids,
                    metadata={"auto_strategy": "shared_role", "role": role},
                ))
                claim(node_ids, "shared_role")

    # Strategy 7: Naming prefix.
    if config.naming_prefix:
        prefix_clusters: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            if node.id in assigned:
                continue
            parts = re.split(r"[-_.]", node.name)
            if len(parts) >= 2:
                prefix = parts[0]
                if len(prefix) >= config.min_prefix_len:
                    prefix_clusters[prefix].append(node.id)
        for prefix, node_ids in prefix_clusters.items():
            if len(node_ids) >= config.min_group_size:
                groups.append(StackMapGroup(
                    id=f"auto:prefix:{prefix.lower()}",
                    name=f"{prefix}",
                    group_type="smart_group",
                    children=node_ids,
                    metadata={"auto_strategy": "naming_prefix", "prefix": prefix},
                ))
                claim(node_ids, "naming_prefix")

    # Strategy 8: VPC.
    if config.vpc_based:
        for vpc_id, node_ids in _cluster_by_property(ir.nodes, "vpc_id", assigned).items():
            if len(node_ids) >= 2:
                groups.append(StackMapGroup(
                    id=f"auto:vpc:{vpc_id}",
                    name=f"VPC {vpc_id[-8:]}",
                    group_type="smart_group",
                    children=node_ids,
                    metadata={"auto_strategy": "vpc", "vpc_id": vpc_id},
                ))
                claim(node_ids, "vpc")

    # Strategy 9: Subnet (opt-in).
    if config.subnet_based:
        for subnet_id, node_ids in _cluster_by_property(ir.nodes, "subnet_id", assigned).items():
            if len(node_ids) >= config.min_group_size:
                groups.append(StackMapGroup(
                    id=f"auto:subnet:{subnet_id}",
                    name=f"Subnet {subnet_id[-8:]}",
                    group_type="smart_group",
                    children=node_ids,
                    metadata={"auto_strategy": "subnet", "subnet_id": subnet_id},
                ))
                claim(node_ids, "subnet")

    # Strategy 10: Region — only emit when the IR spans ≥2 regions.
    if config.region_based:
        regions_seen = {
            (n.metadata.get("region") or n.properties.get("region"))
            for n in ir.nodes
        }
        regions_seen.discard(None)
        regions_seen.discard("")
        if len(regions_seen) >= 2:
            region_clusters: dict[str, list[str]] = defaultdict(list)
            for node in ir.nodes:
                region = node.metadata.get("region") or node.properties.get("region")
                if region:
                    # Region groups span across other strategies — they are
                    # hierarchy parents, not claimers.
                    region_clusters[region].append(node.id)
            for region, node_ids in region_clusters.items():
                if len(node_ids) >= 2:
                    groups.append(StackMapGroup(
                        id=f"auto:region:{region}",
                        name=f"Region {region}",
                        group_type="smart_group",
                        children=node_ids,
                        metadata={"auto_strategy": "region", "region": region},
                    ))

    # Strategy 11: Account — parent-tier only when ≥2 accounts.
    if config.account_based:
        accounts_seen = {
            n.metadata.get("account_id") for n in ir.nodes
        }
        accounts_seen.discard(None)
        accounts_seen.discard("")
        if len(accounts_seen) >= 2:
            account_clusters: dict[str, list[str]] = defaultdict(list)
            for node in ir.nodes:
                account = node.metadata.get("account_id")
                if account:
                    account_clusters[account].append(node.id)
            for account, node_ids in account_clusters.items():
                if len(node_ids) >= 2:
                    groups.append(StackMapGroup(
                        id=f"auto:account:{account}",
                        name=f"Account {account}",
                        group_type="smart_group",
                        children=node_ids,
                        metadata={"auto_strategy": "account", "account_id": account},
                    ))

    # Strategy 12: Connectivity fallback.
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
            groups.append(StackMapGroup(
                id=f"auto:component:{component[0]}",
                name=f"Component ({len(component)} resources)",
                group_type="smart_group",
                children=component,
                metadata={"auto_strategy": "connectivity"},
            ))
            claim(component, "connectivity")

    # Annotate every group with score / reason / signals / categories.
    adj_all = _build_any_adjacency(ir)
    for group in groups:
        _annotate_group(group, ir, nodes_by_id, adj_all)

    # Drop low-confidence duplicates: if a stronger group fully contains a
    # weaker one (or vice versa), keep the stronger.
    groups = _prune_low_confidence(groups, config)

    # Hierarchy (account → region → env → service) — sets ``parent`` only.
    if config.hierarchy:
        _link_hierarchy(groups)

    return groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cluster_by_tag(
    nodes: list[StackMapNode], tag_key: str, assigned: set[str]
) -> dict[str, list[str]]:
    clusters: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node.id in assigned:
            continue
        val = node.tags.get(tag_key)
        if val:
            clusters[val].append(node.id)
    return clusters


def _cluster_by_property(
    nodes: list[StackMapNode], prop_key: str, assigned: set[str]
) -> dict[str, list[str]]:
    clusters: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node.id in assigned:
            continue
        val = node.properties.get(prop_key) or node.metadata.get(prop_key, "")
        if val:
            clusters[val].append(node.id)
    return clusters


def _mk_tag_group(
    *, strategy: str, tag_key: str, tag_value: str,
    node_ids: list[str], name_prefix: str,
) -> StackMapGroup:
    return StackMapGroup(
        id=f"auto:{strategy}:{tag_key}:{_slug(tag_value)}",
        name=f"{name_prefix}{tag_value}",
        group_type="smart_group",
        children=list(node_ids),
        metadata={
            "auto_strategy": strategy,
            "tag_key": tag_key,
            "tag_value": tag_value,
        },
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "x"


def _build_any_adjacency(ir: StackMapIR) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for edge in ir.edges:
        adj[edge.source].add(edge.target)
        adj[edge.target].add(edge.source)
    return adj


def _annotate_group(
    group: StackMapGroup,
    ir: StackMapIR,
    nodes_by_id: dict[str, StackMapNode],
    adj: dict[str, set[str]],
) -> None:
    children = set(group.children)
    size = len(children)
    if size == 0:
        group.metadata.setdefault("confidence", 0.0)
        group.metadata.setdefault("reason", "")
        return

    # Cohesion: fraction of edges that stay inside the group.
    inside = 0
    crossing = 0
    for src, neighbors in adj.items():
        if src not in children:
            continue
        for tgt in neighbors:
            if tgt in children:
                inside += 1
            else:
                crossing += 1
    total = inside + crossing
    cohesion = (inside / total) if total else 0.5

    # Category dominance (top 2 categories as "dominant").
    categories: dict[str, int] = defaultdict(int)
    for cid in children:
        node = nodes_by_id.get(cid)
        if node:
            categories[node.category.value] += 1
    top = sorted(categories.items(), key=lambda kv: -kv[1])[:2]
    dominant = [c for c, _ in top]
    top_count = top[0][1] if top else 0
    category_purity = (top_count / size) if size else 0.0

    # Size score saturates at 4× min threshold (min size 3 → sat at 12).
    size_score = min(size / 12.0, 1.0)

    strategy = group.metadata.get("auto_strategy", "unknown")
    # Strategy-specific baseline priority (explicit business signals beat
    # structural ones).
    strategy_weight = {
        "environment": 0.9,
        "tag": 0.85,
        "team": 0.8,
        "stack": 0.75,
        "module_path": 0.7,
        "shared_role": 0.55,
        "naming_prefix": 0.6,
        "vpc": 0.5,
        "subnet": 0.45,
        "region": 0.4,
        "account": 0.4,
        "connectivity": 0.35,
    }.get(strategy, 0.5)

    confidence = round(
        0.45 * strategy_weight
        + 0.25 * cohesion
        + 0.15 * category_purity
        + 0.15 * size_score,
        3,
    )

    group.metadata["confidence"] = confidence
    group.metadata["signals"] = [strategy]
    group.metadata["dominant_categories"] = dominant
    group.metadata["resource_count"] = size
    group.metadata["cohesion"] = round(cohesion, 3)
    group.metadata["reason"] = _render_reason(group, size, inside, crossing, top)


def _render_reason(
    group: StackMapGroup,
    size: int,
    inside: int,
    crossing: int,
    top_categories: list[tuple[str, int]],
) -> str:
    strategy = group.metadata.get("auto_strategy", "unknown")
    bits: list[str] = []

    if strategy == "environment":
        bits.append(f"{size} resources tagged {group.metadata['tag_key']}={group.metadata['tag_value']}")
    elif strategy == "tag":
        bits.append(f"{size} resources share tag {group.metadata['tag_key']}={group.metadata['tag_value']}")
    elif strategy == "team":
        bits.append(f"{size} resources owned by {group.metadata['tag_value']}")
    elif strategy == "module_path":
        bits.append(f"{size} resources live in Terraform module {group.metadata['module']}")
    elif strategy == "stack":
        bits.append(f"{size} resources from stack {group.metadata['stack_name']}")
    elif strategy == "shared_role":
        short = group.metadata['role'].rsplit('/', 1)[-1]
        bits.append(f"{size} compute resources assume role {short}")
    elif strategy == "naming_prefix":
        bits.append(f"{size} resources named {group.metadata['prefix']}-*")
    elif strategy == "vpc":
        bits.append(f"{size} resources in VPC {group.metadata['vpc_id']}")
    elif strategy == "subnet":
        bits.append(f"{size} resources in subnet {group.metadata['subnet_id']}")
    elif strategy == "region":
        bits.append(f"{size} resources in region {group.metadata['region']}")
    elif strategy == "account":
        bits.append(f"{size} resources in account {group.metadata['account_id']}")
    elif strategy == "connectivity":
        bits.append(f"{size} resources in one connected component")
    else:
        bits.append(f"{size} resources")

    if inside or crossing:
        bits.append(f"{inside} internal / {crossing} crossing edges")
    if top_categories:
        names = ", ".join(name for name, _ in top_categories)
        bits.append(f"dominated by {names}")
    return "; ".join(bits) + "."


def _prune_low_confidence(
    groups: list[StackMapGroup], config: AutoDetectConfig
) -> list[StackMapGroup]:
    # Sort by confidence descending; drop groups whose member set is a full
    # subset of a higher-confidence group AND whose strategy is weaker.
    sorted_groups = sorted(
        groups, key=lambda g: -(g.metadata.get("confidence") or 0.0),
    )
    kept: list[StackMapGroup] = []
    for group in sorted_groups:
        members = set(group.children)
        confidence = group.metadata.get("confidence", 0.0)
        if confidence < config.confidence_floor:
            # Allow only if nothing stronger covers any member.
            covered = any(
                set(prior.children).intersection(members)
                for prior in kept
            )
            if covered:
                continue
        # Drop near-duplicates of a stronger group. Parent-tier strategies
        # (region, account, environment) intentionally contain other
        # groups, so they never cause pruning.
        PARENT_TIERS = {"region", "account", "environment"}
        if any(members.issubset(set(prior.children)) and members != set(prior.children)
               and prior.metadata.get("auto_strategy") not in PARENT_TIERS
               for prior in kept):
            continue
        kept.append(group)
    return kept


def _link_hierarchy(groups: list[StackMapGroup]) -> None:
    """Set ``parent`` pointers so accounts → regions → envs → services.

    A group's parent is the smallest (by member count) parent-tier group
    that fully contains this group's children. Parents are only considered
    from strategies higher up the hierarchy.
    """
    hierarchy_order = {
        "account": 0,
        "region": 1,
        "environment": 2,
        "stack": 3,
        "module_path": 3,
        "tag": 4,
        "team": 4,
        "shared_role": 5,
        "naming_prefix": 5,
        "vpc": 6,
        "subnet": 6,
        "connectivity": 7,
    }
    for group in groups:
        g_strategy = group.metadata.get("auto_strategy", "")
        g_level = hierarchy_order.get(g_strategy, 99)
        g_members = set(group.children)
        best: StackMapGroup | None = None
        for candidate in groups:
            if candidate.id == group.id:
                continue
            c_strategy = candidate.metadata.get("auto_strategy", "")
            c_level = hierarchy_order.get(c_strategy, 99)
            if c_level >= g_level:
                continue
            c_members = set(candidate.children)
            if not g_members.issubset(c_members):
                continue
            if best is None or len(c_members) < len(best.children):
                best = candidate
        if best is not None:
            group.parent = best.id


def score_group(group: StackMapGroup, ir: StackMapIR) -> float:
    """Return the smart-group confidence score used by auto detection."""
    nodes_by_id = {node.id: node for node in ir.nodes}
    _annotate_group(group, ir, nodes_by_id, _build_any_adjacency(ir))
    return float(group.metadata.get("confidence") or 0.0)


def build_reason(group: StackMapGroup, ir: StackMapIR) -> str:
    """Return the human-readable reason text used in the UI."""
    nodes_by_id = {node.id: node for node in ir.nodes}
    _annotate_group(group, ir, nodes_by_id, _build_any_adjacency(ir))
    return str(group.metadata.get("reason") or "")


def build_group_hierarchy(groups: list[StackMapGroup]) -> list[StackMapGroup]:
    """Set parent pointers in-place and return the same group list."""
    _link_hierarchy(groups)
    return groups


def build_group_aggregates(ir: StackMapIR) -> dict:
    """Precompute group-level aggregate nodes and edges for overview rendering."""
    groups = [group for group in ir.groups if group.children]
    node_to_group: dict[str, str] = {}
    for group in groups:
        for child in group.children:
            node_to_group.setdefault(child, group.id)

    aggregate_nodes = [
        {
            "id": group.id,
            "name": group.name,
            "group_type": group.group_type,
            "resource_count": len(group.children),
            "children": group.children,
            "metadata": group.metadata or {},
        }
        for group in groups
    ]

    edge_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for edge in ir.edges:
        source_group = node_to_group.get(edge.source)
        target_group = node_to_group.get(edge.target)
        if not source_group or not target_group or source_group == target_group:
            continue
        edge_counts[(source_group, target_group, edge.edge_type.value)] += 1

    aggregate_edges = [
        {
            "id": f"{source}->{target}:{edge_type}",
            "source": source,
            "target": target,
            "edge_type": edge_type,
            "count": count,
        }
        for (source, target, edge_type), count in sorted(edge_counts.items())
    ]

    return {"groups": aggregate_nodes, "edges_by_group": aggregate_edges}
