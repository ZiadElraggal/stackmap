"""IR dataclasses and abstract base parser."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ResourceCategory(str, Enum):
    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    NETWORK = "network"
    SECURITY = "security"
    MONITORING = "monitoring"
    INTEGRATION = "integration"
    CDN = "cdn"
    DNS = "dns"
    CONTAINER = "container"
    SERVERLESS = "serverless"
    QUEUE = "queue"
    OTHER = "other"


class EdgeType(str, Enum):
    TRIGGERS = "triggers"
    READS_FROM = "reads_from"
    WRITES_TO = "writes_to"
    ROUTES_TO = "routes_to"
    REFERENCES = "references"
    CONTAINS = "contains"
    AUTHENTICATES = "authenticates"


@dataclass
class StackMapNode:
    id: str
    name: str
    resource_type: str
    provider: str
    category: ResourceCategory
    properties: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)
    position_hint: dict = field(default_factory=dict)


@dataclass
class StackMapEdge:
    id: str
    source: str
    target: str
    edge_type: EdgeType
    label: str = ""


@dataclass
class StackMapGroup:
    id: str
    name: str
    group_type: str
    children: list[str] = field(default_factory=list)
    parent: str | None = None


@dataclass
class StackMapIR:
    metadata: dict = field(default_factory=dict)
    nodes: list[StackMapNode] = field(default_factory=list)
    edges: list[StackMapEdge] = field(default_factory=list)
    groups: list[StackMapGroup] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata,
            "nodes": [_node_to_dict(n) for n in self.nodes],
            "edges": [_edge_to_dict(e) for e in self.edges],
            "groups": [_group_to_dict(g) for g in self.groups],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StackMapIR":
        return cls(
            metadata=data.get("metadata", {}),
            nodes=[_node_from_dict(n) for n in data.get("nodes", [])],
            edges=[_edge_from_dict(e) for e in data.get("edges", [])],
            groups=[_group_from_dict(g) for g in data.get("groups", [])],
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "StackMapIR":
        return cls.from_dict(json.loads(json_str))

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json())

    @classmethod
    def read_json(cls, path: str | Path) -> "StackMapIR":
        return cls.from_json(Path(path).read_text())


def _node_to_dict(node: StackMapNode) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "resource_type": node.resource_type,
        "provider": node.provider,
        "category": node.category.value,
        "properties": node.properties,
        "tags": node.tags,
        "position_hint": node.position_hint,
    }


def _node_from_dict(data: dict) -> StackMapNode:
    return StackMapNode(
        id=data["id"],
        name=data["name"],
        resource_type=data["resource_type"],
        provider=data["provider"],
        category=ResourceCategory(data["category"]),
        properties=data.get("properties", {}),
        tags=data.get("tags", {}),
        position_hint=data.get("position_hint", {}),
    )


def _edge_to_dict(edge: StackMapEdge) -> dict:
    return {
        "id": edge.id,
        "source": edge.source,
        "target": edge.target,
        "edge_type": edge.edge_type.value,
        "label": edge.label,
    }


def _edge_from_dict(data: dict) -> StackMapEdge:
    return StackMapEdge(
        id=data["id"],
        source=data["source"],
        target=data["target"],
        edge_type=EdgeType(data["edge_type"]),
        label=data.get("label", ""),
    )


def _group_to_dict(group: StackMapGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "group_type": group.group_type,
        "children": group.children,
        "parent": group.parent,
    }


def _group_from_dict(data: dict) -> StackMapGroup:
    return StackMapGroup(
        id=data["id"],
        name=data["name"],
        group_type=data["group_type"],
        children=data.get("children", []),
        parent=data.get("parent"),
    )


class BaseParser(ABC):
    @abstractmethod
    def parse(self, source_path: str) -> StackMapIR:
        """Parse an infrastructure source file and return the intermediate representation."""
        ...
