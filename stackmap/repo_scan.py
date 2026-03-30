"""Repository-wide source discovery, parsing, and IR merging."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stackmap.parsers.base import EdgeType, StackMapEdge, StackMapGroup, StackMapIR, StackMapNode
from stackmap.parsers.registry import detect_source_type, parse_source

_IGNORED_DIRS = {
    ".git",
    ".claude",
    ".venv",
    ".aws-sam",
    "node_modules",
    ".terraform",
    ".tmp-pkg-venv",
    "__pycache__",
}


@dataclass
class DiscoveredSource:
    path: Path
    source_type: str
    built_from: Path | None = None


@dataclass
class RepoScanResult:
    ir: StackMapIR
    discovered: list[DiscoveredSource]
    parse_errors: list[str]
    link_counts: dict[str, int]


def _walk_files(root: Path, max_depth: int) -> list[Path]:
    files: list[Path] = []
    root = root.resolve()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if len(rel.parts) > max_depth:
            continue
        if any(part in _IGNORED_DIRS for part in rel.parts):
            continue
        files.append(p)
    return files


def _candidate_source_files(root: Path, max_depth: int) -> list[Path]:
    candidates: list[Path] = []
    for path in _walk_files(root, max_depth):
        suffix = path.suffix.lower()
        if suffix in {".tfstate", ".yaml", ".yml", ".json", ".template", ".cfn"}:
            candidates.append(path)
    return sorted(candidates)


def _find_terraform_dirs_missing_state(root: Path, max_depth: int) -> list[Path]:
    dirs_with_tf: set[Path] = set()
    dirs_with_state: set[Path] = set()
    for p in _walk_files(root, max_depth):
        suffix = p.suffix.lower()
        if suffix == ".tf":
            dirs_with_tf.add(p.parent)
        if suffix == ".tfstate" or p.name == "terraform.tfstate":
            dirs_with_state.add(p.parent)
    return sorted(d for d in dirs_with_tf if d not in dirs_with_state)


def discover_sources(
    root: Path,
    include_types: set[str] | None = None,
    max_depth: int = 6,
) -> tuple[list[DiscoveredSource], list[Path]]:
    discovered: list[DiscoveredSource] = []
    for path in _candidate_source_files(root, max_depth):
        try:
            source_type = detect_source_type(path)
        except Exception:
            continue
        if include_types and source_type not in include_types:
            continue
        discovered.append(DiscoveredSource(path=path, source_type=source_type))

    missing_tfstate_dirs = _find_terraform_dirs_missing_state(root, max_depth)
    return discovered, missing_tfstate_dirs


def build_sam_templates(discovered: list[DiscoveredSource]) -> tuple[list[DiscoveredSource], list[str]]:
    """Optionally run `sam build` and replace SAM template sources with transformed output."""
    out: list[DiscoveredSource] = []
    errors: list[str] = []
    for src in discovered:
        if src.source_type != "sam":
            out.append(src)
            continue
        template_dir = src.path.parent
        try:
            subprocess.run(
                ["sam", "build", "--template-file", src.path.name],
                cwd=template_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            built_template = template_dir / ".aws-sam" / "build" / "template.yaml"
            if built_template.exists():
                out.append(DiscoveredSource(path=built_template, source_type="sam", built_from=src.path))
            else:
                out.append(src)
                errors.append(f"SAM build succeeded but no template at {built_template}")
        except FileNotFoundError:
            out.append(src)
            errors.append("SAM CLI not found on PATH; using source SAM templates.")
        except subprocess.CalledProcessError as exc:
            out.append(src)
            stderr = (exc.stderr or "").strip()
            errors.append(f"SAM build failed for {src.path}: {stderr or 'unknown error'}")
    return out, errors


def _iter_string_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, list):
        for item in value:
            values.extend(_iter_string_values(item))
    elif isinstance(value, dict):
        for v in value.values():
            values.extend(_iter_string_values(v))
    return values


def _canonical_strings(node: StackMapNode) -> tuple[set[str], set[str], set[str]]:
    """Return (arns, ids, names) from node properties and canonical fields."""
    arns: set[str] = set()
    ids: set[str] = set()
    names: set[str] = set()

    names.add(node.name)
    ids.add(node.id)

    for key in ("arn", "execution_arn", "role_arn", "state_machine_arn"):
        val = node.properties.get(key)
        if isinstance(val, str) and val:
            arns.add(val)
    for key in ("id", "name", "function_name", "table_name", "bucket", "queue_name", "role_name"):
        val = node.properties.get(key)
        if isinstance(val, str) and val:
            ids.add(val)
            names.add(val)

    return arns, ids, names


def _qualify_node_id(source_key: str, node_id: str) -> str:
    return f"{source_key}::{node_id}"


def merge_sources(
    parsed: list[tuple[DiscoveredSource, StackMapIR]],
    strict_linking: bool = True,
    parse_errors: list[str] | None = None,
) -> RepoScanResult:
    nodes: list[StackMapNode] = []
    edges: list[StackMapEdge] = []
    groups: list[StackMapGroup] = []
    all_parse_errors: list[str] = list(parse_errors or [])

    node_map: dict[tuple[str, str], StackMapNode] = {}
    source_keys: dict[str, str] = {}

    for src, ir in parsed:
        source_key = str(src.path)
        source_keys[source_key] = src.source_type

        id_map: dict[str, str] = {}
        for n in ir.nodes:
            nid = _qualify_node_id(source_key, n.id)
            id_map[n.id] = nid
            merged_node = StackMapNode(
                id=nid,
                name=n.name,
                resource_type=n.resource_type,
                provider=n.provider,
                category=n.category,
                properties={**n.properties},
                tags={**n.tags},
                position_hint={**n.position_hint, "source_file": str(src.path), "source_type": src.source_type},
            )
            nodes.append(merged_node)
            node_map[(source_key, nid)] = merged_node

        for e in ir.edges:
            src_id = id_map.get(e.source)
            tgt_id = id_map.get(e.target)
            if not src_id or not tgt_id:
                continue
            edges.append(
                StackMapEdge(
                    id=f"{src_id}->{tgt_id}:{e.edge_type.value}",
                    source=src_id,
                    target=tgt_id,
                    edge_type=e.edge_type,
                    label=e.label,
                )
            )

        for g in ir.groups:
            children = [id_map[c] for c in g.children if c in id_map]
            parent = id_map[g.parent] if g.parent and g.parent in id_map else None
            groups.append(
                StackMapGroup(
                    id=f"{source_key}::{g.id}",
                    name=g.name,
                    group_type=g.group_type,
                    children=children,
                    parent=parent,
                )
            )

    # Cross-source linking
    arn_index: dict[str, list[str]] = {}
    id_index: dict[str, list[str]] = {}
    name_index: dict[str, list[str]] = {}
    node_by_id: dict[str, StackMapNode] = {n.id: n for n in nodes}
    source_for_node: dict[str, str] = {n.id: str(n.position_hint.get("source_file", "")) for n in nodes}

    for n in nodes:
        arns, ids, names = _canonical_strings(n)
        for a in arns:
            arn_index.setdefault(a, []).append(n.id)
        for i in ids:
            if len(i) >= 3:
                id_index.setdefault(i, []).append(n.id)
        for nm in names:
            if len(nm) >= 3:
                name_index.setdefault(nm.lower(), []).append(n.id)

    edge_seen: set[tuple[str, str, str]] = {(e.source, e.target, e.edge_type.value) for e in edges}
    high = medium = low = 0

    for n in nodes:
        src_file = source_for_node.get(n.id, "")
        values = _iter_string_values(n.properties)
        for val in values:
            confidence = ""
            targets: list[str] = []
            if val in arn_index:
                targets = arn_index[val]
                confidence = "high"
            elif val in id_index:
                targets = id_index[val]
                confidence = "medium"
            elif val.lower() in name_index:
                targets = name_index[val.lower()]
                confidence = "low"
            if not targets:
                continue
            for tgt in targets:
                if tgt == n.id:
                    continue
                if source_for_node.get(tgt, "") == src_file:
                    continue
                if strict_linking and confidence != "high":
                    continue
                if not strict_linking and confidence == "low":
                    # keep low-confidence links disabled unless we later add --very-loose mode
                    continue
                key = (n.id, tgt, EdgeType.REFERENCES.value)
                if key in edge_seen:
                    continue
                edge_seen.add(key)
                if confidence == "high":
                    high += 1
                elif confidence == "medium":
                    medium += 1
                else:
                    low += 1
                edges.append(
                    StackMapEdge(
                        id=f"{n.id}->{tgt}:cross",
                        source=n.id,
                        target=tgt,
                        edge_type=EdgeType.REFERENCES,
                        label=f"cross-source ({confidence})",
                    )
                )

    merged = StackMapIR(
        metadata={
            "source_type": "repo",
            "discovered_sources": [
                {
                    "path": str(src.path),
                    "type": src.source_type,
                    "built_from": str(src.built_from) if src.built_from else None,
                }
                for src, _ir in parsed
            ],
            "strict_linking": strict_linking,
            "total_resources": len(nodes),
            "parse_errors": all_parse_errors,
        },
        nodes=nodes,
        edges=edges,
        groups=groups,
    )
    return RepoScanResult(
        ir=merged,
        discovered=[src for src, _ir in parsed],
        parse_errors=all_parse_errors,
        link_counts={"high": high, "medium": medium, "low": low},
    )


def parse_discovered_sources(discovered: list[DiscoveredSource]) -> tuple[list[tuple[DiscoveredSource, StackMapIR]], list[str]]:
    parsed: list[tuple[DiscoveredSource, StackMapIR]] = []
    errors: list[str] = []
    for src in discovered:
        try:
            _stype, ir = parse_source(src.path)
            parsed.append((src, ir))
        except Exception as exc:
            errors.append(f"{src.path}: {exc}")
    return parsed, errors
