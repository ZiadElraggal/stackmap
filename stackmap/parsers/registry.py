"""Parser registry and source-type detection."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from stackmap.parsers.base import BaseParser, StackMapIR

try:
    import yaml  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    yaml = None


def _is_sam_transform(transform: object) -> bool:
    if transform == "AWS::Serverless-2016-10-31":
        return True
    if isinstance(transform, list):
        return "AWS::Serverless-2016-10-31" in transform
    return False


def detect_source_type(source_path: str | Path) -> str:
    """Auto-detect infrastructure source type from file extension or content."""
    path = Path(source_path)
    if path.suffix == ".tfstate" or "terraform" in path.name.lower():
        return "terraform"
    if path.suffix.lower() in {".template", ".cfn"}:
        return "cloudformation"
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            if yaml is None:
                raise typer.BadParameter(
                    "YAML CloudFormation template detected but PyYAML is not installed."
                )
            from stackmap.parsers.cloudformation import _build_cfn_yaml_loader

            loader = _build_cfn_yaml_loader()
            data = yaml.load(path.read_text(), Loader=loader)
            if not isinstance(data, dict):
                raise ValueError("not a mapping")
            if "AWSTemplateFormatVersion" in data or "Resources" in data:
                if _is_sam_transform(data.get("Transform")):
                    return "sam"
                return "cloudformation"
        except typer.BadParameter:
            raise
        except Exception:
            pass
    if path.suffix.lower() == ".json":
        try:
            raw = path.read_text()
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
                if _is_sam_transform(data.get("Transform")):
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
