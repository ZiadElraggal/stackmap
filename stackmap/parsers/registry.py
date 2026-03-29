"""Parser registry and source-type detection."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from stackmap.parsers.base import BaseParser, StackMapIR


def detect_source_type(source_path: str | Path) -> str:
    """Auto-detect infrastructure source type from file extension or content."""
    path = Path(source_path)
    if path.suffix == ".tfstate" or "terraform" in path.name.lower():
        return "terraform"
    if path.suffix.lower() in {".template", ".cfn"}:
        return "cloudformation"
    if path.suffix.lower() in {".yaml", ".yml", ".json"}:
        try:
            raw = path.read_text()
            if path.suffix.lower() in {".yaml", ".yml"}:
                if "AWS::Serverless-2016-10-31" in raw:
                    return "sam"
                return "cloudformation"
            data = json.loads(raw)
            if (
                isinstance(data, dict)
                and "metadata" in data
                and "nodes" in data
                and "edges" in data
                and "groups" in data
                and isinstance(data.get("nodes"), list)
                and isinstance(data.get("edges"), list)
                and isinstance(data.get("groups"), list)
            ):
                return "stackmap"
            if isinstance(data, dict) and (
                "AWSTemplateFormatVersion" in data
                or "Resources" in data
            ):
                transform = data.get("Transform")
                if transform == "AWS::Serverless-2016-10-31" or (
                    isinstance(transform, list) and "AWS::Serverless-2016-10-31" in transform
                ):
                    return "sam"
                return "cloudformation"
        except Exception:
            pass
    try:
        data = json.loads(path.read_text())
        if "terraform_version" in data:
            return "terraform"
    except Exception:
        pass
    raise typer.BadParameter(
        f"Cannot auto-detect source type for {source_path}. "
        "Supported formats: Terraform state (.tfstate), CloudFormation template (.json/.yaml/.yml), "
        "StackMap IR (.json), "
        "SAM template (.json/.yaml/.yml with AWS::Serverless transform)"
    )


def build_parser(source_type: str) -> BaseParser:
    if source_type == "terraform":
        from stackmap.parsers.terraform import TerraformParser

        return TerraformParser()
    if source_type == "cloudformation":
        from stackmap.parsers.cloudformation import CloudFormationParser

        return CloudFormationParser()
    if source_type == "sam":
        from stackmap.parsers.sam import SamParser

        return SamParser()
    if source_type == "stackmap":
        from stackmap.parsers.stackmap_ir import StackMapIRParser

        return StackMapIRParser()
    raise typer.BadParameter(f"Unsupported source type: {source_type}")


def parse_source(source_path: str | Path) -> tuple[str, StackMapIR]:
    source_type = detect_source_type(source_path)
    parser = build_parser(source_type)
    ir = parser.parse(str(source_path))
    if source_type == "stackmap":
        embedded_source_type = ir.metadata.get("source_type")
        if isinstance(embedded_source_type, str) and embedded_source_type.strip():
            return embedded_source_type, ir
    return source_type, ir
