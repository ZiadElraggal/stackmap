"""Tests for the ASL parser."""

from __future__ import annotations

import json

from stackmap.parsers.asl import classify_edge_label, parse_asl


def _order_saga() -> dict:
    return {
        "Comment": "Order saga",
        "StartAt": "ValidateOrder",
        "States": {
            "ValidateOrder": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": "arn:aws:lambda:us-east-1:123456789012:function:validate-order",
                    "Payload.$": "$",
                },
                "Retry": [
                    {"ErrorEquals": ["States.TaskFailed"], "MaxAttempts": 3, "IntervalSeconds": 2, "BackoffRate": 2.0}
                ],
                "Catch": [
                    {"ErrorEquals": ["States.ALL"], "Next": "HandleFailure", "ResultPath": "$.error"}
                ],
                "Next": "ChargeCard",
            },
            "ChargeCard": {
                "Type": "Task",
                "Resource": "arn:aws:lambda:us-east-1:123456789012:function:charge-card",
                "Catch": [
                    {"ErrorEquals": ["States.ALL"], "Next": "HandleFailure"}
                ],
                "Next": "FanOut",
            },
            "FanOut": {
                "Type": "Parallel",
                "Branches": [
                    {
                        "StartAt": "Notify",
                        "States": {
                            "Notify": {
                                "Type": "Task",
                                "Resource": "arn:aws:states:::sns:publish",
                                "Parameters": {"TopicArn": "arn:aws:sns:us-east-1:123456789012:order-events", "Message.$": "$.order"},
                                "End": True,
                            }
                        },
                    },
                    {
                        "StartAt": "ShipItems",
                        "States": {
                            "ShipItems": {
                                "Type": "Map",
                                "ItemsPath": "$.items",
                                "MaxConcurrency": 5,
                                "Iterator": {
                                    "StartAt": "Ship",
                                    "States": {
                                        "Ship": {
                                            "Type": "Task",
                                            "Resource": "arn:aws:states:::lambda:invoke",
                                            "Parameters": {"FunctionName": "arn:aws:lambda:us-east-1:123456789012:function:ship-item"},
                                            "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "FailShip"}],
                                            "End": True,
                                        },
                                        "FailShip": {"Type": "Fail", "Error": "ShipFailed"},
                                    },
                                },
                                "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "FailBranch"}],
                                "End": True,
                            },
                            "FailBranch": {"Type": "Fail"},
                        },
                    },
                ],
                "Next": "ChooseFollowup",
            },
            "ChooseFollowup": {
                "Type": "Choice",
                "Choices": [
                    {"Variable": "$.method", "StringEquals": "express", "Next": "ExpressThanks"},
                    {
                        "And": [
                            {"Variable": "$.method", "StringEquals": "standard"},
                            {"Variable": "$.vip", "BooleanEquals": True},
                        ],
                        "Next": "VipThanks",
                    },
                ],
                "Default": "StandardThanks",
            },
            "ExpressThanks": {"Type": "Succeed"},
            "VipThanks": {"Type": "Succeed"},
            "StandardThanks": {"Type": "Succeed"},
            "HandleFailure": {"Type": "Fail", "Error": "Biz.Rejected"},
        },
    }


def test_parse_asl_empty_inputs_return_error():
    assert parse_asl(None) == {"error": "empty"}
    assert parse_asl("") == {"error": "empty"}
    assert parse_asl("   ") == {"error": "empty"}
    assert parse_asl("not json")["error"] in ("unparseable", "no_states")
    assert parse_asl({"no": "states"}) == {"error": "no_states"}


def test_parse_asl_order_saga_shape():
    graph = parse_asl(_order_saga())
    assert graph["start_at"] == "ValidateOrder"

    names = [s["name"] for s in graph["states"]]
    # Top-level states plus nested branches/iterators are all present.
    assert "ValidateOrder" in names
    assert "ChargeCard" in names
    assert "Notify" in names  # inside parallel branch
    assert "Ship" in names  # inside map iterator
    assert "FailShip" in names

    # Task classification.
    validate = next(s for s in graph["states"] if s["name"] == "ValidateOrder")
    assert validate["type"] == "Task"
    assert validate["integration"] == "lambda:invoke"
    assert validate["resource_kind"] == "lambda"
    assert validate["resource_arn"] == "arn:aws:lambda:us-east-1:123456789012:function:validate-order"
    assert validate["retry"][0]["max_attempts"] == 3
    assert validate["catch"][0]["next"] == "HandleFailure"

    # Lambda ARN directly as Resource (not integration).
    charge = next(s for s in graph["states"] if s["name"] == "ChargeCard")
    assert charge["resource_kind"] == "lambda"
    assert charge["resource_arn"].endswith("function:charge-card")

    # SNS publish via integration ARN + Parameters.TopicArn.
    notify = next(s for s in graph["states"] if s["name"] == "Notify")
    assert notify["resource_kind"] == "sns"
    assert notify["resource_arn"].endswith("order-events")

    # Parallel branch states grouped.
    fanout = next(s for s in graph["states"] if s["name"] == "FanOut")
    assert fanout["type"] == "Parallel"
    assert len(fanout["branches"]) == 2

    # Map iterator recorded.
    ship_items = next(s for s in graph["states"] if s["name"] == "ShipItems")
    assert ship_items["type"] == "Map"
    assert ship_items["items_path"] == "$.items"
    assert ship_items["max_concurrency"] == 5
    assert ship_items["iterator"]["start_at"] == "Ship"

    # Choice summaries are human-readable.
    choice = next(s for s in graph["states"] if s["name"] == "ChooseFollowup")
    assert choice["type"] == "Choice"
    assert any("$.method" in c["condition_summary"] for c in choice["choices"])
    assert any("AND" in c["condition_summary"] for c in choice["choices"])
    assert choice["default"] == "StandardThanks"

    # Transitions include next, choice, default, and catch entries.
    kinds = {t["kind"] for t in graph["transitions"]}
    assert {"next", "choice", "default", "catch"}.issubset(kinds)

    # Resources list de-duplicates and classifies.
    kinds_seen = {r["kind"] for r in graph["resources"]}
    assert {"lambda", "sns"}.issubset(kinds_seen)


def test_parse_asl_resolver_is_called_with_arns():
    seen: list[str] = []

    def resolver(arn: str) -> str | None:
        seen.append(arn)
        if arn.endswith("validate-order"):
            return "aws_lambda_function.validate_order"
        return None

    graph = parse_asl(_order_saga(), resolver=resolver)
    assert any(a.endswith("validate-order") for a in seen)
    validate = next(s for s in graph["states"] if s["name"] == "ValidateOrder")
    assert validate["resource_node_id"] == "aws_lambda_function.validate_order"
    # Unresolved arns leave node_id as None.
    charge = next(s for s in graph["states"] if s["name"] == "ChargeCard")
    assert charge["resource_node_id"] is None


def test_parse_asl_warnings_cover_common_issues():
    broken = {
        "StartAt": "First",
        "States": {
            "First": {
                "Type": "Task",
                "Resource": "arn:aws:lambda:us-east-1:1:function:first",
                # No Catch — should emit missing_catch.
                # No Next / End — should emit no_terminal.
            },
            "Unreachable": {
                "Type": "Pass",
                "End": True,
            },
            "BadNext": {
                "Type": "Pass",
                "Next": "DoesNotExist",
            },
        },
    }
    graph = parse_asl(broken)
    codes = {w["code"] for w in graph["warnings"]}
    assert "missing_catch" in codes
    assert "unreachable" in codes
    assert "orphan_next" in codes
    assert "no_terminal" in codes


def test_parse_asl_accepts_json_string():
    graph = parse_asl(json.dumps(_order_saga()))
    assert graph.get("start_at") == "ValidateOrder"


def test_parse_asl_sdk_integration_and_edge_labels():
    machine = {
        "StartAt": "PutOrder",
        "States": {
            "PutOrder": {
                "Type": "Task",
                "Resource": "arn:aws:states:::aws-sdk:dynamodb:putItem",
                "Parameters": {"TableName": "arn:aws:dynamodb:us-east-1:1:table/Orders", "Item": {}},
                "End": True,
            },
        },
    }
    graph = parse_asl(machine)
    state = graph["states"][0]
    assert state["resource_kind"] == "aws-sdk"
    assert state["resource_arn"] == "arn:aws:dynamodb:us-east-1:1:table/Orders"
    # Edge classification falls through to the SDK action name.
    assert classify_edge_label("aws-sdk", "aws-sdk:putItem") == "writes"
    assert classify_edge_label("lambda", "lambda:invoke") == "invokes"
    assert classify_edge_label("sns", "sns:publish") == "publishes"
    assert classify_edge_label("sqs", "sqs:sendMessage") == "sends"
    assert classify_edge_label("eventbridge", "events:putEvents") == "emits"
    assert classify_edge_label("stepfunctions", "states:startExecution") == "starts"


def test_parse_asl_sync_pattern_and_distributed_map():
    machine = {
        "StartAt": "FanOutJobs",
        "States": {
            "FanOutJobs": {
                "Type": "Map",
                "ItemProcessor": {
                    "ProcessorConfig": {"Mode": "DISTRIBUTED", "ExecutionType": "STANDARD"},
                    "StartAt": "RunChild",
                    "States": {
                        "RunChild": {
                            "Type": "Task",
                            "Resource": "arn:aws:states:::states:startExecution.sync:2",
                            "Parameters": {
                                "StateMachineArn": "arn:aws:states:us-east-1:1:stateMachine:ChildMachine"
                            },
                            "End": True,
                        }
                    },
                },
                "End": True,
            }
        },
    }

    graph = parse_asl(machine)
    fanout = next(s for s in graph["states"] if s["name"] == "FanOutJobs")
    assert fanout["iterator"]["processor_config"]["Mode"] == "DISTRIBUTED"
    child = next(s for s in graph["states"] if s["name"] == "RunChild")
    assert child["pattern"] == "sync:2"
    assert child["resource_kind"] == "stepfunctions"
    assert child["resource_arn"].endswith("stateMachine:ChildMachine")


def test_parse_asl_wait_and_pass_states():
    machine = {
        "StartAt": "Hold",
        "States": {
            "Hold": {"Type": "Wait", "Seconds": 30, "Next": "Decorate"},
            "Decorate": {"Type": "Pass", "Result": {"ok": True}, "End": True},
        },
    }
    graph = parse_asl(machine)
    hold = next(s for s in graph["states"] if s["name"] == "Hold")
    assert hold["wait_seconds"] == 30
    decorate = next(s for s in graph["states"] if s["name"] == "Decorate")
    assert decorate["end"] is True
    assert "result_summary" in decorate
