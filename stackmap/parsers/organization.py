"""Parser for normalized AWS Organizations export documents."""

from __future__ import annotations

from stackmap.organizations import load_organization_document
from stackmap.parsers.base import BaseParser, StackMapIR


class OrganizationParser(BaseParser):
    """Validate organization JSON and surface it through IR metadata."""

    def parse(self, source_path: str) -> StackMapIR:
        org = load_organization_document(source_path)
        return StackMapIR(
            metadata={
                "source_type": "organization",
                "organization": org.to_dict(),
            }
        )
