from pathlib import Path

from stackmap.graph.diff import compute_diff
from stackmap.parsers.base import StackMapIR


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_compute_diff_from_complex_timeline_fixtures() -> None:
    before = StackMapIR.read_json(FIXTURES / "timeline-before.json")
    after = StackMapIR.read_json(FIXTURES / "timeline-after.json")

    diff = compute_diff(before, after)

    assert diff.summary.added == 2
    assert diff.summary.removed == 1
    assert diff.summary.modified == 1
    assert diff.summary.unchanged == 4

    statuses = {item.node_id: item.status for item in diff.node_diffs}
    assert statuses["queue"] == "added"
    assert statuses["worker"] == "added"
    assert statuses["sns"] == "removed"
    assert statuses["handler"] == "modified"


def test_to_diff_ir_annotates_nodes_edges_and_timestamps() -> None:
    before = StackMapIR.read_json(FIXTURES / "timeline-before.json")
    after = StackMapIR.read_json(FIXTURES / "timeline-after.json")

    diff_ir = compute_diff(before, after).to_diff_ir()

    assert diff_ir.metadata["diff_mode"] is True
    assert diff_ir.metadata["diff_from_scanned_at"] == "2026-03-30T09:00:00+00:00"
    assert diff_ir.metadata["diff_to_scanned_at"] == "2026-03-31T09:00:00+00:00"
    assert diff_ir.metadata["diff_summary"] == {
        "added": 2,
        "removed": 1,
        "modified": 1,
        "unchanged": 4,
    }
    assert diff_ir.metadata["edge_diff_status"]["handler-queue:triggers"] == "added"
    assert diff_ir.metadata["edge_diff_status"]["handler-sns:triggers"] == "removed"

    nodes = {node.id: node for node in diff_ir.nodes}
    assert nodes["queue"].position_hint["diff_status"] == "added"
    assert nodes["sns"].position_hint["diff_status"] == "removed"
    assert nodes["handler"].position_hint["diff_status"] == "modified"
    assert nodes["handler"].position_hint["diff_changes"] == {
        "memory_size": {"old": 256, "new": 512},
        "timeout": {"old": 15, "new": 30},
    }
