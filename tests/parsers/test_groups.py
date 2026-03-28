"""Tests for group extraction."""

from pathlib import Path

from stackmap.parsers.terraform import TerraformParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_complex_has_vpc_groups() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))

    vpc_groups = [g for g in ir.groups if g.group_type == "vpc"]
    assert len(vpc_groups) == 2, f"Expected 2 VPC groups, got {len(vpc_groups)}"


def test_complex_has_subnet_groups() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))

    subnet_groups = [g for g in ir.groups if g.group_type == "subnet"]
    assert len(subnet_groups) >= 4, f"Expected ≥4 subnet groups, got {len(subnet_groups)}"


def test_complex_subnet_groups_have_vpc_parent() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))

    subnet_groups = [g for g in ir.groups if g.group_type == "subnet"]
    for sg in subnet_groups:
        assert sg.parent is not None, f"Subnet group {sg.name} should have a VPC parent"
        assert sg.parent.startswith("group:"), "Parent should be a group ID"


def test_complex_vpc_groups_have_children() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "complex-multi-vpc.tfstate"))

    vpc_groups = [g for g in ir.groups if g.group_type == "vpc"]
    for vg in vpc_groups:
        assert len(vg.children) > 0, f"VPC group {vg.name} should have children"


def test_simple_has_no_vpc_groups() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "simple-lambda-api.tfstate"))
    # Simple fixture has no VPCs
    assert len(ir.groups) == 0
