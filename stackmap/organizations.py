"""AWS Organizations helpers, account extraction, and org overlay support."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import typer
except Exception:  # pragma: no cover
    class _TyperCompat:
        class BadParameter(ValueError):
            pass

    typer = _TyperCompat()

from stackmap.parsers.base import EdgeType, StackMapEdge, StackMapGroup, StackMapIR, StackMapNode

ARN_RE = re.compile(r"^arn:[^:]+:[^:]*:[^:]*:(?P<account>\d{12})(?::|/|$)")
SQS_URL_RE = re.compile(r"^https://sqs\.[^.]+\.amazonaws\.com/(?P<account>\d{12})/")
ACCOUNT_ID_RE = re.compile(r"(?<!\d)(\d{12})(?!\d)")
ACCOUNT_LABEL_RE = re.compile(r"^\d{12}(?:\s*[-:]\s*.+)?$")

ORG_GROUP_TYPES = {"organization_root", "ou", "account"}
ACCOUNT_PROPERTY_KEYS = {
    "arn",
    "execution_arn",
    "role_arn",
    "kms_key_id",
    "function_arn",
    "topic_arn",
    "queue_arn",
    "queue_url",
    "resource_arn",
    "web_acl_arn",
    "certificate_arn",
    "source_arn",
}


@dataclass
class OrganizationDocument:
    org_id: str
    root_id: str
    root_name: str
    ous: list[dict[str, Any]]
    accounts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "org_id": self.org_id,
            "root_id": self.root_id,
            "root_name": self.root_name,
            "ous": self.ous,
            "accounts": self.accounts,
        }


def _extract_account_from_string(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    arn_match = ARN_RE.match(value)
    if arn_match:
        return arn_match.group("account")
    sqs_match = SQS_URL_RE.match(value)
    if sqs_match:
        return sqs_match.group("account")
    if ACCOUNT_LABEL_RE.match(value):
        direct = ACCOUNT_ID_RE.search(value)
        if direct:
            return direct.group(1)
    return None


def _extract_region_from_string(value: str) -> str | None:
    if not value.startswith("arn:"):
        return None
    parts = value.split(":", 5)
    if len(parts) < 6:
        return None
    region = parts[3].strip()
    return region or None


def _iter_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, list):
        for item in value:
            strings.extend(_iter_strings(item))
    elif isinstance(value, dict):
        for item in value.values():
            strings.extend(_iter_strings(item))
    return strings


def derive_account_metadata(node: StackMapNode) -> tuple[str | None, str | None]:
    """Conservatively derive (account_id, region) from node fields and properties."""
    account_candidates: Counter[str] = Counter()
    region_candidates: Counter[str] = Counter()

    def consider(value: str) -> None:
        account = _extract_account_from_string(value)
        if account:
            account_candidates[account] += 1
        region = _extract_region_from_string(value)
        if region:
            region_candidates[region] += 1

    for value in (node.id, node.name):
        consider(value)

    for key in ACCOUNT_PROPERTY_KEYS:
        raw = node.properties.get(key)
        for value in _iter_strings(raw):
            consider(value)

    for value in _iter_strings(node.properties):
        consider(value)

    existing_account = node.metadata.get("account_id")
    if isinstance(existing_account, str) and ACCOUNT_ID_RE.fullmatch(existing_account):
        account_candidates[existing_account] += 10

    existing_region = node.metadata.get("region")
    if isinstance(existing_region, str) and existing_region:
        region_candidates[existing_region] += 10

    account_id = None
    if len(account_candidates) == 1:
        account_id = next(iter(account_candidates))
    elif account_candidates:
        top_account, top_count = account_candidates.most_common(1)[0]
        runner_up = account_candidates.most_common(2)
        if len(runner_up) == 1 or top_count > runner_up[1][1]:
            account_id = top_account

    region = region_candidates.most_common(1)[0][0] if region_candidates else None
    return account_id, region


def annotate_node_account_metadata(nodes: list[StackMapNode]) -> None:
    for node in nodes:
        account_id, region = derive_account_metadata(node)
        if account_id:
            node.metadata.setdefault("account_id", account_id)
            node.position_hint.setdefault("account_id", account_id)
        if region:
            node.metadata.setdefault("region", region)
            node.position_hint.setdefault("region", region)


def load_organization_document(path: str | Path) -> OrganizationDocument:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise typer.BadParameter("Organization file must be a JSON object.")

    required_keys = {"org_id", "root_id", "accounts", "ous"}
    missing = sorted(required_keys - set(data))
    if missing:
        raise typer.BadParameter(
            f"Organization file is missing required keys: {', '.join(missing)}"
        )

    org_id = str(data["org_id"])
    root_id = str(data["root_id"])
    root_name = str(data.get("root_name") or "Root")
    ous = data.get("ous")
    accounts = data.get("accounts")
    if not isinstance(ous, list) or not isinstance(accounts, list):
        raise typer.BadParameter("Organization file must contain list fields `ous` and `accounts`.")

    normalized_ous: list[dict[str, Any]] = []
    for ou in ous:
        if not isinstance(ou, dict):
            raise typer.BadParameter("Each OU entry must be an object.")
        normalized_ous.append(
            {
                "id": str(ou["id"]),
                "name": str(ou["name"]),
                "parent": str(ou.get("parent") or root_id),
                "path": str(ou.get("path") or ""),
            }
        )

    normalized_accounts: list[dict[str, Any]] = []
    for account in accounts:
        if not isinstance(account, dict):
            raise typer.BadParameter("Each account entry must be an object.")
        account_id = str(account["id"])
        if not ACCOUNT_ID_RE.fullmatch(account_id):
            raise typer.BadParameter(f"Invalid AWS account ID in organization file: {account_id}")
        normalized_accounts.append(
            {
                "id": account_id,
                "name": str(account.get("name") or account_id),
                "email": account.get("email"),
                "status": str(account.get("status") or "ACTIVE"),
                "parent": str(account.get("parent") or root_id),
                "ou_path": str(account.get("ou_path") or root_name),
            }
        )

    return OrganizationDocument(
        org_id=org_id,
        root_id=root_id,
        root_name=root_name,
        ous=normalized_ous,
        accounts=normalized_accounts,
    )


def overlay_organization_groups(
    ir: StackMapIR,
    org: OrganizationDocument | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Add account and OU groups around existing infrastructure groups."""
    annotate_node_account_metadata(ir.nodes)

    nodes_by_account: dict[str, list[str]] = {}
    for node in ir.nodes:
        account_id = node.metadata.get("account_id")
        if isinstance(account_id, str) and account_id:
            nodes_by_account.setdefault(account_id, []).append(node.id)

    group_by_id = {group.id: group for group in ir.groups}
    account_group_by_id: dict[str, str] = {}
    existing_org_groups = [group for group in ir.groups if group.group_type in ORG_GROUP_TYPES]
    if existing_org_groups:
        ir.groups = [group for group in ir.groups if group.group_type not in ORG_GROUP_TYPES]
        group_by_id = {group.id: group for group in ir.groups}

    top_level_resource_groups = [g for g in ir.groups if g.parent is None]

    for account_id, child_ids in sorted(nodes_by_account.items()):
        account_group_id = f"group:account:{account_id}"
        account_group_by_id[account_id] = account_group_id
        ir.groups.append(
            StackMapGroup(
                id=account_group_id,
                name=account_id,
                group_type="account",
                children=sorted(set(child_ids)),
                parent=None,
                metadata={"account_id": account_id, "source_kind": "scan"},
            )
        )

    for group in top_level_resource_groups:
        account_counts: Counter[str] = Counter()
        for child_id in group.children:
            child_node = next((node for node in ir.nodes if node.id == child_id), None)
            account_id = child_node.metadata.get("account_id") if child_node else None
            if isinstance(account_id, str) and account_id:
                account_counts[account_id] += 1
        if len(account_counts) == 1:
            account_id = next(iter(account_counts))
            group.parent = account_group_by_id.get(account_id)
            group.metadata.setdefault("account_id", account_id)
            group.metadata.setdefault("source_kind", "scan")

    overlay_metadata: dict[str, Any] = {
        "mapped_account_ids": sorted(nodes_by_account),
        "unmapped_account_ids": [],
        "unscanned_account_ids": [],
    }

    if org is None:
        ir.metadata["organization"] = None
        ir.metadata["organization_overlay"] = overlay_metadata
        return overlay_metadata

    accounts_by_id = {account["id"]: account for account in org.accounts}
    ous_by_id = {ou["id"]: ou for ou in org.ous}
    root_group_id = f"group:org-root:{org.root_id}"
    ou_group_ids: dict[str, str] = {}

    ir.groups.append(
        StackMapGroup(
            id=root_group_id,
            name=org.root_name,
            group_type="organization_root",
            children=sorted(node.id for node in ir.nodes),
            parent=None,
            metadata={"org_id": org.org_id, "org_path": org.root_name},
        )
    )

    sorted_ous = sorted(org.ous, key=lambda ou: len(str(ou.get("path") or "").split("/")))

    for ou in sorted_ous:
        group_id = f"group:ou:{ou['id']}"
        ou_group_ids[ou["id"]] = group_id
        descendant_accounts = [
            account["id"]
            for account in org.accounts
            if account.get("ou_path", "") == (ou.get("path") or f"{org.root_name}/{ou['name']}")
            or account.get("ou_path", "").startswith(f"{ou.get('path')}/")
        ]
        descendant_node_ids = sorted(
            {
                node.id
                for node in ir.nodes
                if node.metadata.get("account_id") in descendant_accounts
            }
        )
        parent_ou = str(ou.get("parent") or org.root_id)
        ir.groups.append(
            StackMapGroup(
                id=group_id,
                name=ou["name"],
                group_type="ou",
                children=descendant_node_ids,
                parent=root_group_id if parent_ou == org.root_id else ou_group_ids.get(parent_ou),
                metadata={
                    "ou_id": ou["id"],
                    "org_path": ou.get("path") or f"{org.root_name}/{ou['name']}",
                    "source_kind": "organization",
                },
            )
        )

    mapped_accounts: set[str] = set()
    scanned_accounts = set(nodes_by_account)
    unmapped_accounts = sorted(scanned_accounts - set(accounts_by_id))
    overlay_metadata["unmapped_account_ids"] = unmapped_accounts
    overlay_metadata["unscanned_account_ids"] = sorted(set(accounts_by_id) - scanned_accounts)

    unmapped_group_id = None
    if unmapped_accounts:
        unmapped_group_id = "group:ou:unmapped"
        ir.groups.append(
            StackMapGroup(
                id=unmapped_group_id,
                name="Unmapped Accounts",
                group_type="ou",
                children=sorted(
                    {
                        node_id
                        for account_id in unmapped_accounts
                        for node_id in nodes_by_account.get(account_id, [])
                    }
                ),
                parent=root_group_id,
                metadata={
                    "ou_id": "unmapped",
                    "org_path": f"{org.root_name}/Unmapped Accounts",
                    "source_kind": "organization",
                },
            )
        )

    for group in ir.groups:
        if group.group_type != "account":
            continue
        account_id = str(group.metadata.get("account_id") or group.name)
        account = accounts_by_id.get(account_id)
        if account is None:
            if strict and account_id in scanned_accounts:
                raise typer.BadParameter(
                    f"Account {account_id} was found in infrastructure data but is missing from the organization file."
                )
            group.parent = unmapped_group_id or root_group_id
            group.metadata["org_path"] = f"{org.root_name}/Unmapped Accounts/{account_id}"
            group.metadata["account_name"] = account_id
            continue
        mapped_accounts.add(account_id)
        group.name = str(account.get("name") or account_id)
        group.parent = root_group_id
        group.metadata["account_name"] = group.name
        group.metadata["org_path"] = account["ou_path"]

        for ou in org.ous:
            path = str(account["ou_path"])
            if path.endswith(f"/{ou['name']}") or f"/{ou['name']}/" in path:
                group.parent = ou_group_ids.get(ou["id"], root_group_id)

    for node in ir.nodes:
        account_id = node.metadata.get("account_id")
        if not isinstance(account_id, str):
            continue
        account = accounts_by_id.get(account_id)
        if account:
            node.metadata.setdefault("account_name", account["name"])
            node.metadata.setdefault("org_path", account["ou_path"])
            node.position_hint.setdefault("org_path", account["ou_path"])
        elif unmapped_group_id:
            unmapped_path = f"{org.root_name}/Unmapped Accounts/{account_id}"
            node.metadata.setdefault("org_path", unmapped_path)
            node.position_hint.setdefault("org_path", unmapped_path)

    ir.metadata["organization"] = org.to_dict()
    ir.metadata["organization_overlay"] = {
        **overlay_metadata,
        "mapped_account_ids": sorted(mapped_accounts),
        "root_group_id": root_group_id,
    }
    return ir.metadata["organization_overlay"]


def infer_cross_account_edges(ir: StackMapIR) -> int:
    node_by_id = {node.id: node for node in ir.nodes}
    edge_seen = {(edge.source, edge.target, edge.edge_type.value) for edge in ir.edges}
    added = 0

    for edge in list(ir.edges):
        source = node_by_id.get(edge.source)
        target = node_by_id.get(edge.target)
        if not source or not target:
            continue
        source_account = source.metadata.get("account_id")
        target_account = target.metadata.get("account_id")
        if not isinstance(source_account, str) or not isinstance(target_account, str):
            continue
        if source_account == target_account:
            continue
        key = (edge.source, edge.target, EdgeType.CROSS_ACCOUNT_REFERENCE.value)
        if key in edge_seen:
            continue
        edge_seen.add(key)
        added += 1
        ir.edges.append(
            StackMapEdge(
                id=f"{edge.source}->{edge.target}:cross-account",
                source=edge.source,
                target=edge.target,
                edge_type=EdgeType.CROSS_ACCOUNT_REFERENCE,
                label=f"{source_account} → {target_account}",
            )
        )
    return added


def build_org_document_from_aws(
    profile: str | None = None,
    region: str | None = None,
    root_id: str | None = None,
) -> OrganizationDocument:
    try:
        import boto3  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "boto3 is required for `stackmap org-import`. Install it with `pip install boto3`."
        ) from exc

    session_kwargs: dict[str, Any] = {}
    if profile:
        session_kwargs["profile_name"] = profile
    if region:
        session_kwargs["region_name"] = region

    session = boto3.session.Session(**session_kwargs)
    client = session.client("organizations")

    organization = client.describe_organization()["Organization"]
    roots = client.list_roots()["Roots"]
    if not roots:
        raise RuntimeError("AWS Organizations returned no roots.")
    root = roots[0]
    selected_root_id = root_id or root["Id"]
    root_name = root.get("Name") or "Root"

    ous: list[dict[str, Any]] = []
    accounts: list[dict[str, Any]] = []
    path_by_parent: dict[str, str] = {selected_root_id: root_name}

    def walk(parent_id: str) -> None:
        base_path = path_by_parent.get(parent_id, root_name)

        ou_paginator = client.get_paginator("list_organizational_units_for_parent")
        for page in ou_paginator.paginate(ParentId=parent_id):
            for ou in page.get("OrganizationalUnits", []):
                ou_path = f"{base_path}/{ou['Name']}"
                ous.append(
                    {
                        "id": ou["Id"],
                        "name": ou["Name"],
                        "parent": parent_id,
                        "path": ou_path,
                    }
                )
                path_by_parent[ou["Id"]] = ou_path
                walk(ou["Id"])

        account_paginator = client.get_paginator("list_accounts_for_parent")
        for page in account_paginator.paginate(ParentId=parent_id):
            for account in page.get("Accounts", []):
                accounts.append(
                    {
                        "id": account["Id"],
                        "name": account["Name"],
                        "email": account.get("Email"),
                        "status": account.get("Status"),
                        "parent": parent_id,
                        "ou_path": base_path,
                    }
                )

    walk(selected_root_id)

    return OrganizationDocument(
        org_id=organization["Id"],
        root_id=selected_root_id,
        root_name=root_name,
        ous=ous,
        accounts=accounts,
    )
