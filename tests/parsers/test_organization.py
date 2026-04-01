from pathlib import Path

from stackmap.organizations import infer_cross_account_edges, load_organization_document, overlay_organization_groups
from stackmap.parsers.base import EdgeType, StackMapIR
from stackmap.repo_scan import discover_sources, merge_sources, parse_discovered_sources

FIXTURES = Path(__file__).parent.parent / "fixtures"
ORG_REPO = FIXTURES / "org_repo"
ORG_DEMO_REPO = FIXTURES / "org_demo_repo"


def test_load_organization_document_round_trips_fixture() -> None:
    org = load_organization_document(ORG_REPO / "org.json")
    assert org.org_id == "o-stackmap"
    assert org.root_name == "Root"
    assert len(org.ous) >= 5
    assert len(org.accounts) >= 6


def test_org_repo_merge_adds_account_and_ou_groups() -> None:
    discovered, _missing = discover_sources(ORG_REPO, max_depth=6)
    parsed, errors = parse_discovered_sources(discovered)
    assert not errors

    result = merge_sources(
        parsed,
        strict_linking=True,
        org_document=load_organization_document(ORG_REPO / "org.json"),
    )
    ir = result.ir

    account_groups = [group for group in ir.groups if group.group_type == "account"]
    ou_groups = [group for group in ir.groups if group.group_type == "ou"]
    assert len(account_groups) >= 6
    assert len(ou_groups) >= 5

    account_ids = {group.metadata.get("account_id") for group in account_groups}
    assert "210000000002" in account_ids
    assert "210000000004" in account_ids

    mapped_nodes = [node for node in ir.nodes if node.metadata.get("org_path")]
    assert mapped_nodes, "Expected organization overlay to annotate nodes with org paths"


def test_org_repo_generates_cross_account_edges() -> None:
    discovered, _missing = discover_sources(ORG_REPO, max_depth=6)
    parsed, errors = parse_discovered_sources(discovered)
    assert not errors

    result = merge_sources(
        parsed,
        strict_linking=True,
        org_document=load_organization_document(ORG_REPO / "org.json"),
    )
    cross_edges = [edge for edge in result.ir.edges if edge.edge_type == EdgeType.CROSS_ACCOUNT_REFERENCE]
    assert cross_edges, "Expected cross-account references in the large org fixture"
    labels = {edge.label for edge in cross_edges}
    assert any("210000000002" in label and "210000000004" in label for label in labels)


def test_overlay_creates_unmapped_bucket_for_unknown_account(tmp_path: Path) -> None:
    ir = StackMapIR.read_json(FIXTURES / "timeline-before.json")
    ir.nodes[0].metadata["account_id"] = "210000009999"
    ir.nodes[1].metadata["account_id"] = "210000009999"

    org = load_organization_document(ORG_REPO / "org.json")
    overlay = overlay_organization_groups(ir, org=org, strict=False)

    assert "210000009999" in overlay["unmapped_account_ids"]
    unmapped = [group for group in ir.groups if group.id == "group:ou:unmapped"]
    assert unmapped


def test_infer_cross_account_edges_converts_existing_refs() -> None:
    ir = StackMapIR.read_json(FIXTURES / "timeline-before.json")
    ir.nodes[0].metadata["account_id"] = "210000000001"
    ir.nodes[1].metadata["account_id"] = "210000000002"
    ir.edges[0].source = ir.nodes[0].id
    ir.edges[0].target = ir.nodes[1].id

    added = infer_cross_account_edges(ir)

    assert added == 1
    assert any(edge.edge_type == EdgeType.CROSS_ACCOUNT_REFERENCE for edge in ir.edges)


def test_realistic_demo_repo_is_discoverable() -> None:
    discovered, missing = discover_sources(ORG_DEMO_REPO, max_depth=6)
    assert not missing
    assert len(discovered) >= 6
