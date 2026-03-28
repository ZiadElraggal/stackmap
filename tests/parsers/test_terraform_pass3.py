"""Tests for Terraform parser Pass 3: Embedded definition parsing."""

from pathlib import Path

from stackmap.parsers.base import EdgeType
from stackmap.parsers.terraform import TerraformParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _edges_between_types(ir, source_type: str, target_type: str, edge_type: EdgeType) -> list:
    node_types = {n.id: n.resource_type for n in ir.nodes}
    return [
        e
        for e in ir.edges
        if node_types.get(e.source) == source_type
        and node_types.get(e.target) == target_type
        and e.edge_type == edge_type
    ]


def _edges_from_name(ir, source_name: str, edge_type: EdgeType) -> list:
    node_names = {n.id: n.name for n in ir.nodes}
    return [
        e for e in ir.edges if node_names.get(e.source) == source_name and e.edge_type == edge_type
    ]


# --- Step Functions ASL parsing ---


def test_step_functions_triggers_lambdas() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))

    sfn_triggers = _edges_between_types(
        ir, "aws_sfn_state_machine", "aws_lambda_function", EdgeType.TRIGGERS
    )
    assert len(sfn_triggers) == 3, (
        f"Step Functions should trigger 3 Lambdas, got {len(sfn_triggers)}"
    )

    target_names = {
        next(n.name for n in ir.nodes if n.id == e.target) for e in sfn_triggers
    }
    assert "ingest-handler" in target_names
    assert "process-worker" in target_names
    assert "store-writer" in target_names


# --- IAM policy parsing ---


def test_iam_infers_lambda_writes_to_dynamodb() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))

    # ingest-handler has dynamodb:PutItem in its policy → writes_to events-table
    writes = _edges_from_name(ir, "ingest-handler", EdgeType.WRITES_TO)
    dynamo_writes = [
        e
        for e in writes
        if any(n.id == e.target and n.name == "events-table" for n in ir.nodes)
    ]
    assert len(dynamo_writes) >= 1, "ingest-handler should write to events-table"


def test_iam_infers_lambda_reads_from_s3() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))

    # process-worker has s3:GetObject + s3:PutObject → writes_to (write takes priority)
    s3_edges = _edges_from_name(ir, "process-worker", EdgeType.WRITES_TO)
    s3_targets = [
        e
        for e in s3_edges
        if any(n.id == e.target and n.resource_type == "aws_s3_bucket" for n in ir.nodes)
    ]
    assert len(s3_targets) >= 1, "process-worker should have data flow edge to S3"


def test_iam_infers_lambda_to_sqs() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))

    # ingest-handler has sqs:SendMessage → writes_to processing-queue
    sqs_edges = _edges_from_name(ir, "ingest-handler", EdgeType.WRITES_TO)
    sqs_targets = [
        e
        for e in sqs_edges
        if any(n.id == e.target and n.resource_type == "aws_sqs_queue" for n in ir.nodes)
    ]
    assert len(sqs_targets) >= 1, "ingest-handler should write to SQS queue"


def test_no_duplicate_edges_after_pass3() -> None:
    parser = TerraformParser()
    ir = parser.parse(str(FIXTURES / "medium-step-functions.tfstate"))
    edge_keys = [(e.source, e.target, e.edge_type) for e in ir.edges]
    assert len(edge_keys) == len(set(edge_keys)), "Duplicate edges found after Pass 3"
