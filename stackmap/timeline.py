"""Build timeline IRs from dated StackMap snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from stackmap.graph.diff import compute_diff
from stackmap.parsers.base import StackMapIR


@dataclass(frozen=True)
class TimelineSnapshot:
    id: str
    label: str
    source: str
    path: Path
    graph: StackMapIR

    def metadata(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "source": self.source,
            "node_count": len(self.graph.nodes),
            "edge_count": len(self.graph.edges),
        }


def _snapshot_id(path: Path, ir: StackMapIR) -> str:
    scanned_at = ir.metadata.get("scanned_at")
    if isinstance(scanned_at, str) and scanned_at:
        return scanned_at
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()


def _snapshot_label(snapshot_id: str, path: Path) -> str:
    try:
        parsed = datetime.fromisoformat(snapshot_id.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return path.stem


def load_timeline_snapshots(history_dir: str | Path) -> list[TimelineSnapshot]:
    """Load every JSON StackMap snapshot in a history directory."""
    root = Path(history_dir)
    snapshots: list[TimelineSnapshot] = []
    for path in sorted(root.glob("*.json")):
        try:
            ir = StackMapIR.read_json(path)
        except Exception:
            continue
        snapshot_id = _snapshot_id(path, ir)
        snapshots.append(
            TimelineSnapshot(
                id=snapshot_id,
                label=_snapshot_label(snapshot_id, path),
                source=str(ir.metadata.get("source_path") or path.name),
                path=path,
                graph=ir,
            )
        )
    snapshots.sort(key=lambda item: item.id)
    return snapshots


def build_timeline_ir(history_dir: str | Path) -> StackMapIR:
    """Build a merged timeline IR from a directory of StackMap JSON files."""
    snapshots = load_timeline_snapshots(history_dir)
    if not snapshots:
        raise ValueError(f"No StackMap JSON snapshots found in {history_dir}")

    active = snapshots[-1].graph
    diffs: list[dict] = []
    for before, after in zip(snapshots, snapshots[1:]):
        diff = compute_diff(before.graph, after.graph)
        diff_dict = diff.to_dict()
        diffs.append(
            {
                "from": before.id,
                "to": after.id,
                "summary": diff_dict["summary"],
                "added": [
                    item["node_id"] for item in diff_dict["node_diffs"] if item["status"] == "added"
                ],
                "removed": [
                    item["node_id"] for item in diff_dict["node_diffs"] if item["status"] == "removed"
                ],
                "changed": [
                    item["node_id"] for item in diff_dict["node_diffs"] if item["status"] == "modified"
                ],
                "node_diffs": diff_dict["node_diffs"],
                "edge_diffs": diff_dict["edge_diffs"],
            }
        )

    timeline = {
        "snapshots": [
            {**snapshot.metadata(), "graph": snapshot.graph.to_dict()} for snapshot in snapshots
        ],
        "diffs": diffs,
    }

    metadata = {
        **active.metadata,
        "timeline_mode": True,
        "timeline_snapshot_count": len(snapshots),
        "active_snapshot_id": snapshots[-1].id,
        "source_path": str(Path(history_dir)),
    }
    return StackMapIR(
        metadata=metadata,
        nodes=list(active.nodes),
        edges=list(active.edges),
        groups=list(active.groups),
        timeline=timeline,
        organization=active.organization,
        aggregates=active.aggregates,
    )


def write_snapshot(ir: StackMapIR, snapshot_dir: str | Path) -> Path:
    """Write a scan result into a history directory using its scanned_at timestamp."""
    root = Path(snapshot_dir)
    root.mkdir(parents=True, exist_ok=True)
    scanned_at = str(ir.metadata.get("scanned_at") or datetime.now(UTC).isoformat())
    safe = (
        scanned_at.replace(":", "")
        .replace("+", "Z")
        .replace("/", "-")
        .replace(" ", "T")
    )
    path = root / f"{safe}.json"
    ir.write_json(path)
    return path
