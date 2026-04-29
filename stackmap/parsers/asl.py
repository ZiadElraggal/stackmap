"""Amazon States Language (ASL) parser.

Turns a Step Functions definition (JSON / YAML / dict) into a structured
``asl_graph`` shape suitable for rendering in the frontend and for emitting
kind-labeled edges in upstream IR parsers.

The goal is to be strictly more useful than the AWS console diagram:
- every state is represented (Task, Choice, Parallel, Map, Wait, Pass,
  Succeed, Fail)
- branches / iterators are preserved recursively
- Catch and Retry are surfaced as first-class transitions
- Task ``Resource`` ARNs are classified (lambda, sqs, sns, dynamodb, ecs,
  glue, athena, batch, eventbridge, stepfunctions, activity, http,
  bedrock, sagemaker, aws-sdk, generic)
- warnings are generated for common footguns (missing catch, unreachable
  state, dangling ``Next``, non-terminal branches)

The function is intentionally pure and free of I/O. Callers (Terraform,
CloudFormation, SAM, live scanner) supply a ``resolver`` that maps ARNs
to StackMap node IDs when they have one; otherwise resources are recorded
with ``node_id=None``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable

Resolver = Callable[[str], str | None]


# Known service integration patterns of the form
# ``arn:aws:states:::<service>:<action>[.pattern]``
_INTEGRATION_KIND: dict[str, str] = {
    "lambda": "lambda",
    "sqs": "sqs",
    "sns": "sns",
    "dynamodb": "dynamodb",
    "ecs": "ecs",
    "batch": "batch",
    "glue": "glue",
    "athena": "athena",
    "emr": "emr",
    "emr-containers": "emr",
    "emr-serverless": "emr",
    "eventbridge": "eventbridge",
    "events": "eventbridge",
    "states": "stepfunctions",
    "stepfunctions": "stepfunctions",
    "apigateway": "apigateway",
    "http": "http",
    "bedrock": "bedrock",
    "sagemaker": "sagemaker",
    "codebuild": "codebuild",
    "mediaconvert": "mediaconvert",
    "databrew": "databrew",
    "elasticmapreduce": "emr",
    "ecr": "ecr",
    "aws-sdk": "aws-sdk",
}


# Short-form action → read/write/trigger classification for edge labels.
_WRITE_ACTIONS = {
    "putitem", "updateitem", "deleteitem", "batchwriteitem",
    "putobject", "deleteobject",
    "sendmessage", "publish",
    "putevents", "putrecord", "putrecords",
    "runtask", "starttask", "starttaskexecution",
    "startjobrun", "startcrawler", "startqueryexecution",
    "startexecution",
    "invokemodel", "invokeagent",
}
_READ_ACTIONS = {
    "getitem", "query", "scan",
    "getobject", "listbucket", "listobjects",
    "receivemessage",
    "describe", "get", "list", "head",
}


def parse_asl(
    definition: str | dict | None,
    *,
    resolver: Resolver | None = None,
) -> dict:
    """Parse an ASL definition into an ``asl_graph`` dict.

    Args:
        definition: JSON string, YAML string, or already-decoded dict. ``None``
            or empty input returns ``{"error": "empty"}``.
        resolver: Optional callable that maps ARNs to StackMap node IDs. When
            provided, each Task's ``resource_node_id`` is populated so the
            frontend can drill down into the target resource.

    Returns:
        A dict matching the ``asl_graph`` contract documented in
        ``PLAN-SMART-GROUPS-AND-STEPFN.md``. Never raises — malformed input
        surfaces as an ``error`` key instead.
    """
    if definition is None or (isinstance(definition, str) and not definition.strip()):
        return {"error": "empty"}

    data: Any
    if isinstance(definition, dict):
        data = definition
    elif isinstance(definition, str):
        data = _load_definition(definition)
        if data is None:
            return {"error": "unparseable"}
    else:
        return {"error": "unsupported_type"}

    if not isinstance(data, dict) or not isinstance(data.get("States"), dict):
        return {"error": "no_states"}

    resolve = resolver or (lambda _arn: None)

    # Build flat state list, transitions, and resource index by walking the
    # top-level machine plus any nested Parallel branches / Map iterators.
    states: list[dict] = []
    transitions: list[dict] = []
    resources: dict[str, dict] = {}
    state_names: set[str] = set()

    _walk_machine(
        data,
        parent_path=(),
        states=states,
        transitions=transitions,
        resources=resources,
        state_names=state_names,
        resolve=resolve,
    )

    warnings = _compute_warnings(data, states, transitions, state_names)

    return {
        "start_at": data.get("StartAt"),
        "timeout_seconds": data.get("TimeoutSeconds"),
        "version": data.get("Version"),
        "comment": data.get("Comment"),
        "states": states,
        "transitions": transitions,
        "resources": list(resources.values()),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Definition loading
# ---------------------------------------------------------------------------


def _load_definition(text: str) -> dict | None:
    """Parse JSON first, fall back to YAML if available."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        import yaml  # type: ignore
    except ImportError:
        return None
    try:
        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else None
    except yaml.YAMLError:
        return None


# ---------------------------------------------------------------------------
# Walker
# ---------------------------------------------------------------------------


def _walk_machine(
    machine: dict,
    *,
    parent_path: tuple[str, ...],
    states: list[dict],
    transitions: list[dict],
    resources: dict[str, dict],
    state_names: set[str],
    resolve: Resolver,
) -> None:
    state_dict = machine.get("States")
    if not isinstance(state_dict, dict):
        return

    for name, spec in state_dict.items():
        if not isinstance(spec, dict):
            continue
        qualified = _qualify(parent_path, name)
        state_names.add(qualified)
        state_type = spec.get("Type", "Unknown")

        entry: dict[str, Any] = {
            "name": name,
            "qualified_name": qualified,
            "type": state_type,
            "path": list(parent_path),
            "comment": spec.get("Comment"),
        }

        # Common fields present on most state types.
        for src, dst in (
            ("InputPath", "input_path"),
            ("OutputPath", "output_path"),
            ("ResultPath", "result_path"),
            ("ResultSelector", "result_selector"),
        ):
            if src in spec:
                entry[dst] = spec[src]

        if spec.get("End") is True:
            entry["end"] = True
        if "Next" in spec:
            entry["next"] = spec["Next"]
            transitions.append({
                "from": qualified,
                "to": _qualify(parent_path, spec["Next"]),
                "kind": "next",
            })

        if state_type == "Task":
            _fill_task(
                entry, spec, qualified, parent_path,
                transitions=transitions, resources=resources, resolve=resolve,
            )
        elif state_type == "Choice":
            _fill_choice(entry, spec, qualified, parent_path, transitions=transitions)
        elif state_type == "Parallel":
            _fill_parallel(
                entry, spec, qualified, parent_path,
                states=states, transitions=transitions,
                resources=resources, state_names=state_names, resolve=resolve,
            )
        elif state_type == "Map":
            _fill_map(
                entry, spec, qualified, parent_path,
                states=states, transitions=transitions,
                resources=resources, state_names=state_names, resolve=resolve,
            )
        elif state_type == "Wait":
            _fill_wait(entry, spec)
        elif state_type == "Pass":
            if "Result" in spec:
                entry["result_summary"] = _summarize_value(spec["Result"])
            if "Parameters" in spec:
                entry["parameters_summary"] = _summarize_parameters(spec["Parameters"])
        elif state_type == "Fail":
            if "Error" in spec:
                entry["error"] = spec["Error"]
            if "Cause" in spec:
                entry["cause"] = spec["Cause"]
            entry["end"] = True
        elif state_type == "Succeed":
            entry["end"] = True

        # Retry / Catch apply to Task, Parallel, Map.
        if state_type in ("Task", "Parallel", "Map"):
            entry["retry"] = _parse_retry(spec.get("Retry"))
            entry["catch"] = _parse_catch(
                spec.get("Catch"), qualified, parent_path, transitions=transitions,
            )
            if "TimeoutSeconds" in spec:
                entry["timeout_seconds"] = spec["TimeoutSeconds"]
            if "HeartbeatSeconds" in spec:
                entry["heartbeat_seconds"] = spec["HeartbeatSeconds"]

        states.append(entry)


def _fill_task(
    entry: dict,
    spec: dict,
    qualified: str,
    parent_path: tuple[str, ...],
    *,
    transitions: list[dict],
    resources: dict[str, dict],
    resolve: Resolver,
) -> None:
    resource = spec.get("Resource", "")
    integration, pattern, kind = _classify_resource(resource)
    entry["integration"] = integration
    entry["pattern"] = pattern
    entry["resource_kind"] = kind
    resolved_arn: str | None = None

    # Task ``Resource`` is one of:
    # - Lambda ARN directly: arn:aws:lambda:...:function:foo
    # - Integration ARN: arn:aws:states:::lambda:invoke — the *actual* target
    #   sits in Parameters.FunctionName / Parameters.TableName / etc.
    if isinstance(resource, str) and resource.startswith("arn:aws:") and not resource.startswith("arn:aws:states:"):
        resolved_arn = resource

    params = spec.get("Parameters") if isinstance(spec.get("Parameters"), dict) else None
    args = spec.get("Arguments") if isinstance(spec.get("Arguments"), dict) else None
    param_source = params or args

    if param_source:
        entry["parameters_summary"] = _summarize_parameters(param_source)
        # Try to pull a concrete target out of Parameters for SDK / service
        # integrations (FunctionName, TableName, QueueUrl, TopicArn, StateMachineArn...).
        target_arn = _extract_target_arn(kind, integration, param_source)
        if target_arn:
            resolved_arn = target_arn

    if resolved_arn:
        entry["resource_arn"] = resolved_arn
        node_id = resolve(resolved_arn)
        entry["resource_node_id"] = node_id
        existing = resources.get(resolved_arn)
        if existing is None:
            resources[resolved_arn] = {
                "arn": resolved_arn,
                "kind": kind,
                "integration": integration,
                "pattern": pattern,
                "node_id": node_id,
                "states": [qualified],
            }
        else:
            existing["states"].append(qualified)
            # Prefer a resolvable node_id if a later state resolves it.
            if not existing.get("node_id") and node_id:
                existing["node_id"] = node_id
    else:
        entry["resource_arn"] = None
        entry["resource_node_id"] = None


def _fill_choice(
    entry: dict,
    spec: dict,
    qualified: str,
    parent_path: tuple[str, ...],
    *,
    transitions: list[dict],
) -> None:
    choices: list[dict] = []
    for choice in spec.get("Choices", []) or []:
        if not isinstance(choice, dict):
            continue
        nxt = choice.get("Next")
        summary = _summarize_choice(choice)
        choices.append({
            "condition_summary": summary,
            "next": nxt,
        })
        if nxt:
            transitions.append({
                "from": qualified,
                "to": _qualify(parent_path, nxt),
                "kind": "choice",
                "label": summary,
            })
    entry["choices"] = choices
    default = spec.get("Default")
    if default:
        entry["default"] = default
        transitions.append({
            "from": qualified,
            "to": _qualify(parent_path, default),
            "kind": "default",
        })


def _fill_parallel(
    entry: dict,
    spec: dict,
    qualified: str,
    parent_path: tuple[str, ...],
    *,
    states: list[dict],
    transitions: list[dict],
    resources: dict[str, dict],
    state_names: set[str],
    resolve: Resolver,
) -> None:
    branches_out: list[dict] = []
    for idx, branch in enumerate(spec.get("Branches", []) or []):
        if not isinstance(branch, dict):
            continue
        branch_path = parent_path + (f"{qualified}[branch {idx}]",)
        branch_start = branch.get("StartAt")
        branch_entry = {
            "start_at": branch_start,
            "states": [],
        }
        branches_out.append(branch_entry)
        before = len(states)
        _walk_machine(
            branch,
            parent_path=branch_path,
            states=states,
            transitions=transitions,
            resources=resources,
            state_names=state_names,
            resolve=resolve,
        )
        # Record which states belong to this branch for UI grouping.
        branch_entry["states"] = [s["qualified_name"] for s in states[before:]]
    entry["branches"] = branches_out


def _fill_map(
    entry: dict,
    spec: dict,
    qualified: str,
    parent_path: tuple[str, ...],
    *,
    states: list[dict],
    transitions: list[dict],
    resources: dict[str, dict],
    state_names: set[str],
    resolve: Resolver,
) -> None:
    if "ItemsPath" in spec:
        entry["items_path"] = spec["ItemsPath"]
    if "MaxConcurrency" in spec:
        entry["max_concurrency"] = spec["MaxConcurrency"]
    # Classic ASL uses ``Iterator``; Distributed Map uses ``ItemProcessor``.
    iterator = spec.get("Iterator") or spec.get("ItemProcessor")
    if not isinstance(iterator, dict):
        entry["iterator"] = None
        return
    iter_path = parent_path + (f"{qualified}[iter]",)
    iter_entry = {
        "start_at": iterator.get("StartAt"),
        "processor_config": iterator.get("ProcessorConfig"),
        "states": [],
    }
    before = len(states)
    _walk_machine(
        iterator,
        parent_path=iter_path,
        states=states,
        transitions=transitions,
        resources=resources,
        state_names=state_names,
        resolve=resolve,
    )
    iter_entry["states"] = [s["qualified_name"] for s in states[before:]]
    entry["iterator"] = iter_entry


def _fill_wait(entry: dict, spec: dict) -> None:
    for src, dst in (
        ("Seconds", "wait_seconds"),
        ("SecondsPath", "wait_seconds_path"),
        ("Timestamp", "wait_timestamp"),
        ("TimestampPath", "wait_timestamp_path"),
    ):
        if src in spec:
            entry[dst] = spec[src]


# ---------------------------------------------------------------------------
# Retry / Catch / Choice helpers
# ---------------------------------------------------------------------------


def _parse_retry(retry: Any) -> list[dict]:
    if not isinstance(retry, list):
        return []
    out: list[dict] = []
    for item in retry:
        if not isinstance(item, dict):
            continue
        out.append({
            "error_equals": list(item.get("ErrorEquals", []) or []),
            "interval_seconds": item.get("IntervalSeconds"),
            "max_attempts": item.get("MaxAttempts"),
            "backoff_rate": item.get("BackoffRate"),
            "max_delay_seconds": item.get("MaxDelaySeconds"),
            "jitter_strategy": item.get("JitterStrategy"),
        })
    return out


def _parse_catch(
    catch: Any,
    qualified: str,
    parent_path: tuple[str, ...],
    *,
    transitions: list[dict],
) -> list[dict]:
    if not isinstance(catch, list):
        return []
    out: list[dict] = []
    for item in catch:
        if not isinstance(item, dict):
            continue
        errors = list(item.get("ErrorEquals", []) or [])
        nxt = item.get("Next")
        out.append({
            "error_equals": errors,
            "next": nxt,
            "result_path": item.get("ResultPath"),
        })
        if nxt:
            transitions.append({
                "from": qualified,
                "to": _qualify(parent_path, nxt),
                "kind": "catch",
                "error_equals": errors,
            })
    return out


def _summarize_choice(choice: dict) -> str:
    """Render a compact, human-readable condition string for a Choice rule."""
    # Strip the ``Next`` key so it doesn't show up in the summary.
    body = {k: v for k, v in choice.items() if k != "Next" and k != "Comment"}
    return _render_choice_expr(body)


_COMPARATORS = {
    "StringEquals": "==",
    "StringEqualsPath": "==",
    "StringLessThan": "<",
    "StringLessThanEquals": "<=",
    "StringGreaterThan": ">",
    "StringGreaterThanEquals": ">=",
    "StringMatches": "matches",
    "NumericEquals": "==",
    "NumericEqualsPath": "==",
    "NumericLessThan": "<",
    "NumericLessThanEquals": "<=",
    "NumericGreaterThan": ">",
    "NumericGreaterThanEquals": ">=",
    "BooleanEquals": "==",
    "BooleanEqualsPath": "==",
    "TimestampEquals": "==",
    "TimestampLessThan": "<",
    "TimestampLessThanEquals": "<=",
    "TimestampGreaterThan": ">",
    "TimestampGreaterThanEquals": ">=",
    "IsPresent": "is_present",
    "IsNull": "is_null",
    "IsNumeric": "is_numeric",
    "IsString": "is_string",
    "IsBoolean": "is_boolean",
    "IsTimestamp": "is_timestamp",
}


def _render_choice_expr(expr: Any) -> str:
    if not isinstance(expr, dict) or not expr:
        return ""
    if "And" in expr and isinstance(expr["And"], list):
        parts = [_render_choice_expr(e) for e in expr["And"]]
        return " AND ".join(p for p in parts if p)
    if "Or" in expr and isinstance(expr["Or"], list):
        parts = [_render_choice_expr(e) for e in expr["Or"]]
        inner = " OR ".join(p for p in parts if p)
        return f"({inner})" if inner else ""
    if "Not" in expr and isinstance(expr["Not"], dict):
        inner = _render_choice_expr(expr["Not"])
        return f"NOT ({inner})" if inner else ""

    var = expr.get("Variable")
    for key, op in _COMPARATORS.items():
        if key in expr:
            value = expr[key]
            if op.startswith("is_"):
                return f"{op}({var})" if isinstance(value, bool) and value else f"NOT {op}({var})"
            return f"{var} {op} {_format_literal(value)}"
    return ""


def _format_literal(value: Any) -> str:
    if isinstance(value, str):
        return f"'{value}'"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# ---------------------------------------------------------------------------
# Resource classification
# ---------------------------------------------------------------------------


_INTEGRATION_PREFIX = "arn:aws:states:::"
# Valid ``.pattern`` suffixes on a service integration ARN.
_INTEGRATION_PATTERN_RE = re.compile(r"\.(sync(?::\d+)?|waitForTaskToken)$")
_ARN_RE = re.compile(
    r"^arn:(?P<partition>aws[a-z-]*):(?P<service>[a-zA-Z0-9-]+):[a-z0-9-]*:\d*:"
)


def _classify_resource(resource: Any) -> tuple[str | None, str | None, str]:
    """Return (integration, pattern, kind) for a Task Resource string.

    Handles the three ARN shapes Step Functions accepts as Task targets:
    - Service integration:  ``arn:aws:states:::lambda:invoke``
    - Service integration with pattern: ``…:sqs:sendMessage.waitForTaskToken``
    - SDK integration:      ``arn:aws:states:::aws-sdk:dynamodb:putItem``
    - Direct resource ARN:  ``arn:aws:lambda:us-east-1:123:function:foo``
    """
    if not isinstance(resource, str) or not resource:
        return None, None, "unknown"

    if resource.startswith(_INTEGRATION_PREFIX):
        body = resource[len(_INTEGRATION_PREFIX):]
        pattern: str | None = None
        m = _INTEGRATION_PATTERN_RE.search(body)
        if m:
            pattern = m.group(1)
            body = body[: m.start()]
        if not body:
            return None, pattern, "unknown"
        parts = body.split(":")
        # Activity ARN uses a different shape and is caught below, but SDK
        # integrations put ``aws-sdk`` as the first segment and the real
        # service as the second.
        if parts[0] == "aws-sdk":
            service = parts[1] if len(parts) > 1 else "aws-sdk"
            kind = "aws-sdk"
            integration = ":".join(parts[:3]) if len(parts) >= 2 else "aws-sdk"
            return integration, pattern, kind
        service = parts[0]
        action = parts[1] if len(parts) > 1 else None
        kind = _INTEGRATION_KIND.get(service, service or "unknown")
        integration = f"{service}:{action}" if action else service
        return integration, pattern, kind

    if resource.startswith("arn:aws:states:") and ":activity:" in resource:
        return "activity", None, "activity"

    if resource.startswith("arn:aws:"):
        svc_match = _ARN_RE.match(resource)
        if svc_match:
            service = svc_match.group("service")
            return service, "request_response", _INTEGRATION_KIND.get(service, service)

    return None, None, "unknown"


def _extract_target_arn(kind: str, integration: str | None, params: dict) -> str | None:
    """Pull a concrete ARN/identifier from Parameters based on integration kind."""
    # Lambda
    if kind == "lambda":
        fn = params.get("FunctionName") or params.get("FunctionName.$")
        if isinstance(fn, str) and fn.startswith("arn:aws:lambda:"):
            return fn
    # DynamoDB
    if kind == "dynamodb":
        tbl = params.get("TableName") or params.get("TableName.$")
        if isinstance(tbl, str) and tbl.startswith("arn:aws:dynamodb:"):
            return tbl
    # SQS
    if kind == "sqs":
        qurl = params.get("QueueUrl") or params.get("QueueUrl.$")
        if isinstance(qurl, str) and qurl.startswith("arn:aws:sqs:"):
            return qurl
    # SNS
    if kind == "sns":
        topic = params.get("TopicArn") or params.get("TopicArn.$")
        if isinstance(topic, str) and topic.startswith("arn:aws:sns:"):
            return topic
    # Step Functions nested
    if kind == "stepfunctions":
        sm = params.get("StateMachineArn") or params.get("StateMachineArn.$")
        if isinstance(sm, str) and sm.startswith("arn:aws:states:"):
            return sm
    # ECS
    if kind == "ecs":
        td = params.get("TaskDefinition") or params.get("TaskDefinition.$")
        if isinstance(td, str) and td.startswith("arn:aws:ecs:"):
            return td
    # EventBridge
    if kind == "eventbridge":
        entries = params.get("Entries")
        if isinstance(entries, list) and entries:
            bus = entries[0].get("EventBusName") if isinstance(entries[0], dict) else None
            if isinstance(bus, str) and bus.startswith("arn:aws:events:"):
                return bus
    # Generic: any ARN value looks like a target.
    for value in params.values():
        if isinstance(value, str) and value.startswith("arn:aws:"):
            return value
    return None


# ---------------------------------------------------------------------------
# Summaries & warnings
# ---------------------------------------------------------------------------


def _summarize_parameters(params: Any, limit: int = 6) -> str:
    if not isinstance(params, dict):
        return ""
    keys = list(params.keys())[:limit]
    suffix = "" if len(keys) == len(params) else f", +{len(params) - len(keys)} more"
    return f"keys: {', '.join(keys)}{suffix}" if keys else ""


def _summarize_value(value: Any, limit: int = 80) -> str:
    rendered = json.dumps(value, default=str) if not isinstance(value, str) else value
    if len(rendered) > limit:
        return rendered[: limit - 1] + "…"
    return rendered


def _compute_warnings(
    machine: dict,
    states: list[dict],
    transitions: list[dict],
    state_names: set[str],
) -> list[dict]:
    warnings: list[dict] = []

    # Targets that any transition points at (qualified).
    target_qualified = {t["to"] for t in transitions if t.get("to") in state_names}

    # Entry points: the top-level StartAt plus every branch/iterator StartAt.
    entry_qualified: set[str] = set()
    start = machine.get("StartAt")
    if start and start in state_names:
        entry_qualified.add(start)
    for state in states:
        if state["type"] == "Parallel":
            for branch in state.get("branches", []) or []:
                # branch["states"] are qualified; StartAt is local to branch
                if not branch.get("states"):
                    continue
                # First state of the branch is the effective entry.
                entry_qualified.add(branch["states"][0])
        elif state["type"] == "Map":
            it = state.get("iterator")
            if it and it.get("states"):
                entry_qualified.add(it["states"][0])

    reachable = target_qualified | entry_qualified

    # Missing catch on Task (classic footgun).
    for state in states:
        if state["type"] == "Task" and not state.get("catch"):
            warnings.append({
                "state": state["qualified_name"],
                "code": "missing_catch",
                "message": "Task has no Catch — any failure terminates the execution.",
            })

    # Unreachable states.
    for state in states:
        qname = state["qualified_name"]
        if qname in reachable:
            continue
        warnings.append({
            "state": qname,
            "code": "unreachable",
            "message": "State is defined but never targeted by Next, Default, Catch, or a branch/iterator StartAt.",
        })

    # Orphan Next / Default / Catch references.
    for t in transitions:
        if t.get("to") and t["to"] not in state_names:
            warnings.append({
                "state": t.get("from"),
                "code": "orphan_next",
                "message": f"Transition ({t.get('kind')}) points at unknown state '{t['to']}'.",
            })

    # Non-terminal states: no Next, no End, not Succeed/Fail.
    for state in states:
        if state["type"] in ("Succeed", "Fail"):
            continue
        if state.get("end"):
            continue
        if state.get("next"):
            continue
        if state["type"] == "Choice":
            # Choice is terminal-by-branch: every branch/default leads elsewhere.
            continue
        warnings.append({
            "state": state["qualified_name"],
            "code": "no_terminal",
            "message": "State has no Next and is not End/Succeed/Fail — execution would stall here.",
        })

    return warnings


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _qualify(parent_path: tuple[str, ...], name: str) -> str:
    """Qualified state name — keeps states in branches/iterators uniquely addressable."""
    if not parent_path:
        return name
    return f"{'::'.join(parent_path)}::{name}"


def iter_task_resources(asl_graph: dict) -> Iterable[dict]:
    """Iterate over Task states with resolvable resource info. Convenience for parsers."""
    for state in asl_graph.get("states", []) or []:
        if state.get("type") != "Task":
            continue
        arn = state.get("resource_arn")
        if not arn:
            continue
        yield state


def classify_edge_label(kind: str, integration: str | None) -> str:
    """Pick a short edge label for IR edges emitted from Task states."""
    if not integration:
        return "invokes"
    action = (integration.split(":", 1)[1] if ":" in integration else integration).lower()
    if kind == "lambda":
        return "invokes"
    if kind == "stepfunctions":
        return "starts"
    if kind == "sqs":
        return "sends"
    if kind == "sns":
        return "publishes"
    if kind == "eventbridge":
        return "emits"
    if kind == "activity":
        return "polls"
    if action in _WRITE_ACTIONS:
        return "writes"
    if any(action.startswith(r) for r in _READ_ACTIONS):
        return "reads"
    return "invokes"
