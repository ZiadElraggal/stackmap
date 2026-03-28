"""Tests for IR dataclasses and serialization."""

import json
import tempfile
from pathlib import Path

from stackmap.parsers.base import (
    EdgeType,
    ResourceCategory,
    StackMapEdge,
    StackMapGroup,
    StackMapIR,
    StackMapNode,
)


def _make_sample_ir() -> StackMapIR:
    return StackMapIR(
        metadata={"source": "test", "version": "1.0"},
        nodes=[
            StackMapNode(
                id="aws_lambda.my_func",
                name="my-func",
                resource_type="aws_lambda_function",
                provider="aws",
                category=ResourceCategory.COMPUTE,
                properties={"runtime": "python3.12", "memory_size": 256},
                tags={"env": "prod"},
                position_hint={"tier": "backend", "weight": 3},
            ),
            StackMapNode(
                id="aws_dynamodb.my_table",
                name="my-table",
                resource_type="aws_dynamodb_table",
                provider="aws",
                category=ResourceCategory.DATABASE,
                properties={"billing_mode": "PAY_PER_REQUEST"},
                tags={"env": "prod"},
                position_hint={"tier": "data", "weight": 4},
            ),
        ],
        edges=[
            StackMapEdge(
                id="aws_lambda.my_func->aws_dynamodb.my_table",
                source="aws_lambda.my_func",
                target="aws_dynamodb.my_table",
                edge_type=EdgeType.WRITES_TO,
                label="DynamoDB PutItem",
            ),
        ],
        groups=[
            StackMapGroup(
                id="vpc-123",
                name="main-vpc",
                group_type="vpc",
                children=["aws_lambda.my_func", "aws_dynamodb.my_table"],
                parent=None,
            ),
        ],
    )


def test_ir_to_dict_roundtrip() -> None:
    ir = _make_sample_ir()
    data = ir.to_dict()
    restored = StackMapIR.from_dict(data)

    assert len(restored.nodes) == 2
    assert len(restored.edges) == 1
    assert len(restored.groups) == 1
    assert restored.nodes[0].id == "aws_lambda.my_func"
    assert restored.nodes[0].category == ResourceCategory.COMPUTE
    assert restored.edges[0].edge_type == EdgeType.WRITES_TO
    assert restored.groups[0].children == [
        "aws_lambda.my_func",
        "aws_dynamodb.my_table",
    ]


def test_ir_json_roundtrip() -> None:
    ir = _make_sample_ir()
    json_str = ir.to_json()
    parsed = json.loads(json_str)

    assert parsed["metadata"]["source"] == "test"
    assert len(parsed["nodes"]) == 2
    assert parsed["nodes"][0]["category"] == "compute"
    assert parsed["edges"][0]["edge_type"] == "writes_to"

    restored = StackMapIR.from_json(json_str)
    assert restored.nodes[0].name == "my-func"
    assert restored.edges[0].label == "DynamoDB PutItem"


def test_ir_file_roundtrip() -> None:
    ir = _make_sample_ir()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test-ir.json"
        ir.write_json(path)

        assert path.exists()
        restored = StackMapIR.read_json(path)
        assert len(restored.nodes) == 2
        assert restored.metadata["version"] == "1.0"
