"""Parsers for already-generated StackMap JSON payloads."""

import json
from pathlib import Path

from stackmap.graph.diff import DiffSummary, EdgeDiff, NodeDiff, StackMapDiff
from stackmap.parsers.base import BaseParser, StackMapIR, _edge_from_dict, _node_from_dict


class StackMapIRParser(BaseParser):
    """Load a precomputed StackMap IR document from JSON."""

    def parse(self, source_path: str) -> StackMapIR:
        return StackMapIR.read_json(source_path)


class StackMapDiffParser(BaseParser):
    """Load a precomputed StackMap diff JSON payload and convert it to diff IR."""

    def parse(self, source_path: str) -> StackMapIR:
        data = json.loads(Path(source_path).read_text())

        node_diffs = [
            NodeDiff(
                node_id=item["node_id"],
                status=item["status"],
                node=_node_from_dict(item["node"]),
                changes=item.get("changes"),
            )
            for item in data.get("node_diffs", [])
        ]
        edge_diffs = [
            EdgeDiff(
                edge_id=item["edge_id"],
                status=item["status"],
                edge=_edge_from_dict(item["edge"]),
            )
            for item in data.get("edge_diffs", [])
        ]
        summary_data = data.get("summary", {})
        diff = StackMapDiff(
            from_metadata=data.get("from_metadata", {}),
            to_metadata=data.get("to_metadata", {}),
            node_diffs=node_diffs,
            edge_diffs=edge_diffs,
            summary=DiffSummary(
                added=summary_data.get("added", 0),
                removed=summary_data.get("removed", 0),
                modified=summary_data.get("modified", 0),
                unchanged=summary_data.get("unchanged", 0),
            ),
        )
        return diff.to_diff_ir()
