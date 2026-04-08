"""Tests for drift detection engine."""

from stackmap.drift.engine import DriftStatus, compute_drift
from stackmap.parsers.base import (
    EdgeType,
    ResourceCategory,
    StackMapEdge,
    StackMapIR,
    StackMapNode,
)


def _node(id: str, name: str, rtype: str, props: dict | None = None) -> StackMapNode:
    return StackMapNode(
        id=id,
        name=name,
        resource_type=rtype,
        provider="aws",
        category=ResourceCategory.SERVERLESS,
        properties=props or {},
    )


def _edge(src: str, tgt: str, etype: EdgeType = EdgeType.TRIGGERS) -> StackMapEdge:
    return StackMapEdge(id=f"{src}->{tgt}", source=src, target=tgt, edge_type=etype)


class TestDriftBasic:
    def test_identical_irs_all_in_sync(self) -> None:
        nodes = [_node("fn1", "my-lambda", "aws_lambda_function", {"runtime": "python3.12", "memory_size": 256})]
        iac = StackMapIR(nodes=list(nodes))
        live = StackMapIR(nodes=list(nodes))

        report = compute_drift(iac, live)

        assert report.summary.in_sync == 1
        assert report.summary.drifted == 0
        assert report.summary.missing == 0
        assert report.summary.extra == 0

    def test_missing_in_live(self) -> None:
        iac = StackMapIR(nodes=[
            _node("fn1", "lambda-a", "aws_lambda_function"),
            _node("fn2", "lambda-b", "aws_lambda_function"),
        ])
        live = StackMapIR(nodes=[
            _node("fn1", "lambda-a", "aws_lambda_function"),
        ])

        report = compute_drift(iac, live)

        assert report.summary.missing == 1
        missing = [i for i in report.items if i.status == DriftStatus.MISSING_IN_LIVE]
        assert len(missing) == 1
        assert missing[0].resource_name == "lambda-b"

    def test_extra_in_live(self) -> None:
        iac = StackMapIR(nodes=[
            _node("fn1", "lambda-a", "aws_lambda_function"),
        ])
        live = StackMapIR(nodes=[
            _node("fn1", "lambda-a", "aws_lambda_function"),
            _node("fn2", "lambda-rogue", "aws_lambda_function"),
        ])

        report = compute_drift(iac, live)

        assert report.summary.extra == 1
        extra = [i for i in report.items if i.status == DriftStatus.EXTRA_IN_LIVE]
        assert len(extra) == 1
        assert extra[0].resource_name == "lambda-rogue"

    def test_drifted_property(self) -> None:
        iac = StackMapIR(nodes=[
            _node("fn1", "my-fn", "aws_lambda_function", {"runtime": "python3.11", "memory_size": 256}),
        ])
        live = StackMapIR(nodes=[
            _node("fn1", "my-fn", "aws_lambda_function", {"runtime": "python3.12", "memory_size": 512}),
        ])

        report = compute_drift(iac, live)

        assert report.summary.drifted == 1
        drifted = [i for i in report.items if i.status == DriftStatus.DRIFTED]
        assert len(drifted) == 1
        assert "runtime" in drifted[0].drifted_fields
        assert drifted[0].drifted_fields["runtime"]["iac"] == "python3.11"
        assert drifted[0].drifted_fields["runtime"]["live"] == "python3.12"
        assert "memory_size" in drifted[0].drifted_fields


class TestDriftSeverity:
    def test_critical_security_group_missing(self) -> None:
        iac = StackMapIR(nodes=[_node("sg1", "web-sg", "aws_security_group")])
        live = StackMapIR(nodes=[])

        report = compute_drift(iac, live)

        missing = [i for i in report.items if i.status == DriftStatus.MISSING_IN_LIVE]
        assert missing[0].severity == "critical"

    def test_critical_drifted_ingress(self) -> None:
        iac = StackMapIR(nodes=[
            _node("sg1", "web-sg", "aws_security_group", {"ingress": [{"port": 443}]}),
        ])
        live = StackMapIR(nodes=[
            _node("sg1", "web-sg", "aws_security_group", {"ingress": [{"port": 443}, {"port": 22}]}),
        ])

        report = compute_drift(iac, live)

        drifted = [i for i in report.items if i.status == DriftStatus.DRIFTED]
        assert drifted[0].severity == "critical"

    def test_warning_lambda_config_drift(self) -> None:
        iac = StackMapIR(nodes=[
            _node("fn1", "my-fn", "aws_lambda_function", {"runtime": "python3.11"}),
        ])
        live = StackMapIR(nodes=[
            _node("fn1", "my-fn", "aws_lambda_function", {"runtime": "python3.12"}),
        ])

        report = compute_drift(iac, live)

        drifted = [i for i in report.items if i.status == DriftStatus.DRIFTED]
        assert drifted[0].severity == "warning"


class TestDriftEdges:
    def test_edge_drift_detected(self) -> None:
        nodes = [
            _node("fn1", "handler", "aws_lambda_function"),
            _node("db1", "table", "aws_dynamodb_table"),
        ]
        iac = StackMapIR(
            nodes=list(nodes),
            edges=[_edge("fn1", "db1", EdgeType.WRITES_TO)],
        )
        live = StackMapIR(
            nodes=list(nodes),
            edges=[],  # edge missing in live
        )

        report = compute_drift(iac, live)

        assert report.summary.edge_missing >= 1


class TestDriftReport:
    def test_serialization(self) -> None:
        iac = StackMapIR(nodes=[
            _node("fn1", "lambda-a", "aws_lambda_function", {"runtime": "python3.11"}),
        ])
        live = StackMapIR(nodes=[
            _node("fn1", "lambda-a", "aws_lambda_function", {"runtime": "python3.12"}),
        ])

        report = compute_drift(iac, live)
        d = report.to_dict()

        assert "items" in d
        assert "summary" in d
        assert "scanned_at" in d
        assert d["summary"]["drifted"] == 1

    def test_to_drift_ir(self) -> None:
        iac = StackMapIR(
            nodes=[_node("fn1", "lambda-a", "aws_lambda_function")],
            metadata={"source_type": "terraform"},
        )
        live = StackMapIR(nodes=[
            _node("fn1", "lambda-a", "aws_lambda_function"),
            _node("fn2", "lambda-rogue", "aws_lambda_function"),
        ])

        report = compute_drift(iac, live)
        drift_ir = report.to_drift_ir(iac)

        assert drift_ir.metadata.get("drift_mode") is True
        assert drift_ir.metadata.get("drift_summary") is not None
        # Annotated nodes have drift_status in position_hint
        for node in drift_ir.nodes:
            assert "drift_status" in node.position_hint


class TestDriftEmpty:
    def test_empty_irs(self) -> None:
        report = compute_drift(StackMapIR(), StackMapIR())
        assert report.summary.total_iac == 0
        assert report.summary.total_live == 0

    def test_iac_empty_live_has_resources(self) -> None:
        live = StackMapIR(nodes=[_node("fn1", "fn", "aws_lambda_function")])
        report = compute_drift(StackMapIR(), live)
        assert report.summary.extra == 1
        assert report.summary.missing == 0
