from pathlib import Path

import pytest
typer = pytest.importorskip("typer")

from stackmap.parsers.registry import detect_source_type


def test_detect_source_type_cloudformation_yaml(tmp_path: Path) -> None:
    source = tmp_path / "template.yaml"
    source.write_text(
        "\n".join(
            [
                "AWSTemplateFormatVersion: '2010-09-09'",
                "Resources:",
                "  Bucket:",
                "    Type: AWS::S3::Bucket",
            ]
        )
    )

    assert detect_source_type(source) == "cloudformation"


def test_detect_source_type_sam_yaml(tmp_path: Path) -> None:
    source = tmp_path / "template.yaml"
    source.write_text(
        "\n".join(
            [
                "Transform: AWS::Serverless-2016-10-31",
                "Resources:",
                "  ApiFn:",
                "    Type: AWS::Serverless::Function",
            ]
        )
    )

    assert detect_source_type(source) == "sam"


def test_detect_source_type_rejects_non_template_yaml(tmp_path: Path) -> None:
    source = tmp_path / "pnpm-lock.yaml"
    source.write_text("lockfileVersion: '9.0'\npackages: {}\n")

    with pytest.raises(typer.BadParameter):
        detect_source_type(source)


def test_detect_source_type_organization_json(tmp_path: Path) -> None:
    source = tmp_path / "org.json"
    source.write_text(
        """
        {
          "org_id": "o-example",
          "root_id": "r-root",
          "accounts": [{"id": "210000000001", "name": "prod", "ou_path": "Root/Engineering"}],
          "ous": [{"id": "ou-eng", "name": "Engineering", "parent": "r-root"}]
        }
        """
    )

    assert detect_source_type(source) == "organization"
