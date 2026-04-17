# StackMap — Smart Grouping v2 & Step Functions Viewer

Two focused upgrades layered on top of the 0.4.0 foundation:

1. **Smart Grouping v2** — lift the current heuristic grouper from "good enough to make big graphs readable" to "actually explains the architecture". New signals, hierarchy, confidence scoring, and UI-visible reasons.
2. **Step Functions Extended Viewer** — an in-app state machine diagram that is strictly better than the AWS console: clear flow, resolved resources, catch/retry branches, parallel/map visualization, and drill-down to the target Lambda/SQS/DDB/etc.

Both assume the current codebase state (audited 2026-04-16):
- `stackmap/grouping/engine.py` (tag, naming prefix, VPC, connectivity strategies; flat groups)
- `stackmap/grouping/suggest.py` (tag / prefix / VPC suggestions for `.stackmap/groups.yaml`)
- `frontend/stores/graph.ts` → `buildSmartGroupComponentSummaries()` promotes `smart_group` entries into the component landing page
- `frontend/components/ComponentLanding.vue` → "Smart Components" grid (recent commit 6a3e652)
- Step Functions today: parsed shallowly in `stackmap/parsers/terraform.py` (Lambda ARNs only via `_extract_task_resources`), scanned in `stackmap/aws_live/scanner.py:_collect_stepfunctions` but the ASL is discarded after regex ARN extraction, and **the frontend has no state-machine-aware rendering at all**.

---

## Improvement 1 — Smart Grouping v2

**User story.** "The landing page groups my resources reasonably, but I can't tell *why* they were grouped, and it misses obvious axes like env/region/account/Terraform module. I want tighter, more explainable groups — and I want to nest them: `prod → payments-service → api-tier`."

### Goals

- More signals (env, team, region, account, Terraform module path, CloudFormation stack, shared IAM role, shared subnet).
- Hierarchical groups (a group can have a parent; UI collapses along the tree).
- Confidence / quality score per auto-detected group, surfaced in the UI.
- Human-readable "reason" per group ("grouped by tag `service=payments` — 14 resources, 11 connected").
- Config-surface upgrades so power users can tune thresholds per strategy in `.stackmap/groups.yaml`.

### Data contract

Extend `StackMapGroup.metadata` with a stable shape. Frontend already tolerates arbitrary keys, so this is additive:

```jsonc
{
  "id": "auto:tag:service:payments",
  "name": "Payments",
  "group_type": "smart_group",
  "parent": "auto:env:prod",          // NEW — optional hierarchy pointer
  "children": ["aws_lambda_function.pay_intent", "..."],
  "metadata": {
    "auto_strategy": "tag",
    "tag_key": "service",
    "tag_value": "payments",
    "reason": "14 resources share tag service=payments; 11 are connected.",
    "confidence": 0.84,               // NEW — 0..1, used to rank/demote groups
    "signals": ["tag", "connectivity"],// NEW — all strategies that agreed
    "dominant_categories": ["compute","database"], // NEW — computed in engine
    "icon": "compute",
    "color": "#3b82f6"
  }
}
```

`AutoDetectConfig` grows strategy-specific knobs (non-breaking defaults):

```python
@dataclass
class AutoDetectConfig:
    enabled: bool = True
    tag_keys: list[str] = field(default_factory=lambda: [
        "service", "project", "app", "component", "workload",
    ])
    env_tag_keys: list[str] = field(default_factory=lambda: [
        "env", "environment", "stage", "tier",
    ])
    team_tag_keys: list[str] = field(default_factory=lambda: [
        "team", "owner", "squad", "department",
    ])
    naming_prefix: bool = True
    min_group_size: int = 3
    min_prefix_len: int = 2
    vpc_based: bool = True
    subnet_based: bool = False
    region_based: bool = True           # NEW — multi-region scans
    account_based: bool = True          # NEW — org scans
    module_path_based: bool = True      # NEW — Terraform / CFN nested stack
    shared_role_based: bool = True      # NEW — IAM role co-assumers
    hierarchy: bool = True              # NEW — env → service nesting
    max_depth: int = 2
    confidence_floor: float = 0.35      # Auto-groups below this are hidden
```

### Backend surface

`stackmap/grouping/engine.py`

- New strategies (ordered; earlier claims nodes first, same as today):
  1. Explicit user rules from `.stackmap/groups.yaml` (unchanged).
  2. **Environment** — `env`/`environment`/`stage`/`tier` tags; also detect `-prod-`, `-stg-`, `-dev-` in names.
  3. **Service/workload tags** — existing `service/project/app` plus new `component/workload`.
  4. **Team/owner tags** (parented under env if both exist).
  5. **Terraform module path** — parse `node.metadata["source_module"]` (Terraform parser already records module path; plumb it through where missing).
  6. **CloudFormation stack / SAM app** — use `node.metadata["stack_name"]` when present.
  7. **Shared IAM role** — reuse the policy-parsing path in `terraform.py:_parse_iam_policies` to bucket any two+ compute nodes assuming the same role into an "Assumes role X" group (low confidence, only surfaces when nothing stronger wins).
  8. **Naming prefix** (unchanged, but honors `min_prefix_len`).
  9. **VPC / subnet**.
  10. **Region** (groups-per-region only if the graph spans ≥2 regions).
  11. **Account** (groups-per-account only in org scans; becomes the root of the hierarchy).
  12. **Connectivity** fallback (unchanged).

- New helper `score_group(group, ir) -> float` that combines:
  - `size_score` — saturates at `min_group_size × 4`.
  - `cohesion` — fraction of in-group edges vs. crossing edges (uses `ir.edges`).
  - `category_purity` — how dominant the top 1–2 categories are.
  - `tag_agreement` — if multiple signals point at the same cluster (+0.2 per extra signal).
  - Output clamped to `[0, 1]`; saved as `metadata["confidence"]`.

- New helper `build_reason(group) -> str` that renders a one-sentence human explanation using `metadata` (e.g. `"14 resources share tag service=payments; 11 are connected."`).

- `apply_smart_groups()` + `auto_detect_groups()` both populate `metadata.reason`, `confidence`, `signals`, `dominant_categories`.

- New `build_group_hierarchy(groups) -> list[StackMapGroup]`:
  - Takes the flat list from existing strategies.
  - Links env groups as parents of service groups whose members are a subset of the env group's members.
  - Links account groups as parents of env/region groups.
  - Writes `parent` pointer on the child; the existing `children` field stays as leaf node IDs (no functional rewrite of the data model).

- `suggest_groups()` in `suggest.py` gets parallel additions: env/team/module suggestions, dedup against tag suggestions, and a `confidence` hint written into the suggested YAML so the user sees why each rule was proposed.

### Frontend surface

`frontend/stores/graph.ts`

- Extend the `StackMapGroup.metadata` TS interface with the new keys (`reason`, `confidence`, `signals`, `dominant_categories`, `parent`).
- In `buildSmartGroupComponentSummaries()`:
  - Sort groups primarily by `metadata.confidence`, tiebreak by size.
  - Drop groups whose `metadata.confidence < auto_detect.confidence_floor` **unless** no better grouping exists for their members.
  - Populate a new `ComponentSummary.reason` string from `metadata.reason` (fallback to current "grouped by X" synthesis).
  - Populate `ComponentSummary.parentGroupId` from `metadata.parent`.

`frontend/components/ComponentLanding.vue`

- Under each smart-component card, render a monospace "why" caption using `component.reason`.
- Add a small confidence pip (●●○, `high/medium/low`) derived from `metadata.confidence`.
- Support hierarchy: when a component has `parentGroupId`, group the secondary grid under headers for each parent (env → services, account → envs). One-level of nesting is enough; deeper trees collapse.
- New "Group filter" chip row at the top of the landing page: `All · Prod · Staging · Team Payments · VPC vpc-1234` — clicking filters `primarySummaries`.

`frontend/components/DetailPanel.vue`

- In the existing "Smart group reason" block, show the full `metadata.reason` text and a chip row for `signals`.

### CLI / config surface

- `.stackmap/groups.yaml` gets top-level `auto_detect:` sub-keys matching the new dataclass (backwards compatible — missing keys fall back to defaults).
- `stackmap groups suggest` (existing? if not, thin wrapper over `suggest_groups`) prints rules with `# confidence: 0.78` comments so humans can triage before committing.

### Ship checklist

- [x] `AutoDetectConfig` extended; `load_grouping_config` parses new keys.
- [x] New strategy functions in `engine.py` (env, team, module, stack, shared role, region, account).
- [x] `score_group` + `build_reason` + `build_group_hierarchy` helpers with unit tests in `tests/grouping/test_engine.py`.
- [x] `suggest_groups` emits env/team/module suggestions with confidence comments.
- [x] `graph.ts` consumes `reason` / `confidence` / `parent`.
- [x] `ComponentLanding.vue` renders reason caption, confidence pip, filter chips, parent sections.
- [x] `DetailPanel.vue` shows reason + signals.
- [x] Fixture test: Terraform sample with mixed env/service tags produces hierarchical prod/payments groups.
- [x] Fixture test: AWS-live scan with two regions + two accounts produces region/account roots.
- [x] Docs pass: README + `docs/smart-groups.md` screenshots/examples.

---

## Improvement 2 — Step Functions Extended Viewer

**User story.** "When I click a `state_machine` node, I want a diagram that's clearer than the AWS console — every state, every transition, every catch/retry, every Parallel branch, every Map iterator — and I want to click a Task and jump to the target Lambda/SQS/DDB node in my StackMap graph. Show me what the console hides."

### Goals

- Parse Amazon States Language (ASL) into a structured, first-class `asl_graph` persisted on the state machine node.
- Resolve every Task `Resource` — not just Lambda — including `arn:aws:states:::aws-sdk:<service>:<action>` and `.sync` / `.waitForTaskToken` variants, linking to the matching StackMap node when possible.
- Render a rich `StateMachineViewer.vue` in the DetailPanel: swim-lane-style vertical flow, collapsible Parallel branches, Map iterator preview, Choice rule branches, Catch/Retry branches, per-state metadata inspector.
- Optional: overlay real execution stats (durations, error rates) when an execution history is available from the live scan.

### Data contract

New property on `aws_sfn_state_machine` nodes (Terraform, CloudFormation, SAM, and live scan):

```jsonc
{
  "asl_graph": {
    "start_at": "ValidateOrder",
    "timeout_seconds": 3600,
    "version": "1.0",
    "comment": "…",
    "states": [
      {
        "name": "ValidateOrder",
        "type": "Task",
        "resource_arn": "arn:aws:lambda:us-east-1:…:function:validate-order",
        "resource_kind": "lambda",
        "resource_node_id": "aws_lambda_function.validate_order",  // linkback into StackMap graph; null if unresolved
        "integration": "lambda:invoke",                             // parsed from Resource ARN
        "pattern": "request_response",                              // request_response | sync | waitForTaskToken | .sync:2 | null
        "input_path": "$.order",
        "result_path": "$.validated",
        "parameters_summary": "keys: orderId, customerId",          // small preview, never full body
        "timeout_seconds": 30,
        "heartbeat_seconds": null,
        "retry": [
          { "error_equals": ["States.TaskFailed"], "interval_seconds": 2, "max_attempts": 3, "backoff_rate": 2.0 }
        ],
        "catch": [
          { "error_equals": ["States.ALL"], "next": "HandleFailure", "result_path": "$.error" }
        ],
        "next": "ChargeCard",
        "end": false
      },
      {
        "name": "ChooseShipping",
        "type": "Choice",
        "choices": [
          { "condition_summary": "$.method == 'express'", "next": "ExpressShip" },
          { "condition_summary": "$.method == 'standard'", "next": "StandardShip" }
        ],
        "default": "StandardShip"
      },
      {
        "name": "ParallelFanout",
        "type": "Parallel",
        "branches": [
          { "start_at": "…", "states": [ /* recursive */ ] },
          { "start_at": "…", "states": [ /* recursive */ ] }
        ],
        "next": "Aggregate",
        "retry": [...],
        "catch": [...]
      },
      {
        "name": "FanOutItems",
        "type": "Map",
        "iterator": { "start_at": "…", "states": [ /* recursive */ ] },
        "items_path": "$.items",
        "max_concurrency": 10,
        "next": "…"
      },
      { "name": "HandleFailure", "type": "Fail", "error": "Biz.Rejected", "cause": "…" },
      { "name": "Done", "type": "Succeed" }
    ],
    "transitions": [
      { "from": "ValidateOrder", "to": "ChargeCard", "kind": "next" },
      { "from": "ValidateOrder", "to": "HandleFailure", "kind": "catch", "error_equals": ["States.ALL"] },
      { "from": "ChooseShipping", "to": "ExpressShip", "kind": "choice", "label": "$.method == 'express'" }
    ],
    "resources": [
      { "arn": "arn:aws:lambda:…:function:validate-order", "kind": "lambda", "node_id": "aws_lambda_function.validate_order" },
      { "arn": "arn:aws:dynamodb:…:table/Orders",         "kind": "dynamodb", "node_id": null }
    ],
    "warnings": [
      { "state": "ChargeCard", "code": "missing_catch", "message": "Task has no Catch — any failure terminates the execution." },
      { "state": "OldRetry",   "code": "unreachable",   "message": "State is defined but never targeted." }
    ]
  }
}
```

`asl_graph` is always absent for non-state-machine nodes and always present (even if parse-failed, as `{"error": "..."}`) for `aws_sfn_state_machine` when the ASL was available.

### Backend surface

New module `stackmap/parsers/asl.py`:

```python
def parse_asl(definition: str | dict, *, resolver: ResourceResolver | None = None) -> dict:
    """Parse ASL into the asl_graph contract above. Resolver maps ARNs → StackMap node IDs."""
```

- Accepts `str` (JSON or YAML, as SAM emits YAML) or already-decoded `dict`.
- Walks top-level `States`, recurses into `Branches` / `Iterator` / `ItemProcessor` (Distributed Map).
- Extracts:
  - `Type`, `Next`, `End`, `InputPath`, `ResultPath`, `OutputPath`, `Parameters`, `Arguments`, `ItemsPath`, `MaxConcurrency`, `TimeoutSeconds`, `HeartbeatSeconds`.
  - For `Task`: `Resource` → split `arn:aws:states:::<service>:<action>[.<pattern>]` into `integration` + `pattern`; resolve `resource_arn` via `resolver`; classify `resource_kind` (lambda, sqs, sns, dynamodb, ecs, glue, athena, batch, emr, eventbridge, apigw, bedrock, activity, http, sagemaker, `aws-sdk`, …).
  - `Retry[]` / `Catch[]` arrays flattened into per-state lists *and* emitted as `transitions` entries with `kind=retry|catch`.
  - `Choice.Choices[]` → summarize each `BooleanEquals`/`NumericEquals`/`StringMatches`/nested `And`/`Or` as a compact string (`"$.x > 5 AND $.y == 'ok'"`).
- Produces the `warnings` list:
  - `missing_catch` — any Task without `Catch`.
  - `unreachable` — states never targeted by `Next`/`Default`/`Catch`/`Choice`/`Start`.
  - `orphan_next` — `Next` pointing at a nonexistent state.
  - `no_terminal` — branch with no `End`/`Succeed`/`Fail`/`Next`.
- Pure, no I/O — suitable for both offline (Terraform/CFN) and live (boto3) callers.

Integrations:

- `stackmap/parsers/terraform.py::_parse_step_function_definitions`
  - Replace the Lambda-only `_extract_task_resources` with a call to `parse_asl`, feeding a resolver that maps `arn_index` → node ID.
  - For every `asl_graph.resources[i]` with a resolvable `node_id`, emit a `TRIGGERS` edge (already done) **plus** use the integration kind as the edge label ("invokes", "publishes", "writes", "queries"). Reuse existing `_WRITE_ACTIONS` / `_READ_ACTIONS` maps for SDK integrations.
  - Write `asl_graph` into `node.properties["asl_graph"]`.

- `stackmap/parsers/cloudformation.py`
  - `AWS::StepFunctions::StateMachine` — read `DefinitionString` (or `Definition` / `DefinitionS3Location` — S3 fetch is out of scope; record as warning).
  - `AWS::Serverless::StateMachine` — read `DefinitionUri` (YAML/JSON on disk, resolve relative to template dir) *or* inline `Definition`.
  - Feed `parse_asl` with a resolver that maps logical IDs and ARNs.

- `stackmap/aws_live/scanner.py::_collect_stepfunctions`
  - Stop relying on the raw regex; call `parse_asl(definition, resolver=...)` and persist `asl_graph`.
  - Emit edges from `asl_graph.resources[i].node_id` (where resolvable) instead of ARN substrings — removes false positives on ARNs that appear in `Parameters` but aren't actually called.
  - Fetch recent execution history (`list_executions` with `maxResults=25`) on demand from the viewer and write a compact `asl_graph.recent_executions` summary: `[{status, start, duration_ms, failed_state}]`. Gated by a UI button so it doesn't hammer the API.

### Frontend surface

New store getter in `frontend/stores/graph.ts`:

```typescript
export function getAslGraph(nodeId: string): AslGraph | null {
  const node = graphStore.nodes.find(n => n.id === nodeId)
  return (node?.properties?.asl_graph as AslGraph) ?? null
}
```

With a matching `types/asl.ts` mirroring the data contract above.

New component `frontend/components/StateMachineViewer.vue`:

- Props: `:node="StackMapNode"`. Reads `asl_graph` from properties; renders nothing + a friendly empty state if missing.
- Layout: top-down flow with a left gutter for state names and a right gutter for per-state metadata. Nodes connected by SVG arrows drawn behind the card column (uses the same SVG helpers as the existing `GraphEdge.vue`).
- State card anatomy:
  - Header: state name · type badge (Task / Choice / Parallel / Map / Wait / Pass / Succeed / Fail) · pattern tag (`.sync`, `.waitForTaskToken`, `request_response`).
  - Body: resolved resource chip — clickable, calls `store.focusNode(resource_node_id)` so the graph re-centers on the target; grayed-out if unresolved ARN.
  - Collapsed by default: input/output paths, parameters summary, timeout, heartbeat.
  - Retry / Catch chips rendered as colored pills under the card; clicking a Catch pill drops a dashed arrow to the target state.
- `Parallel` states render as horizontally stacked branch columns with a join bar; each branch is a mini recursive viewer, collapsible.
- `Map` states render the iterator inline, once, with an "×N" multiplier badge.
- `Choice` states fan out to each `next` with the condition string as the arrow label; a `Default` arrow is dashed.
- Warnings surface:
  - Banner at the top of the viewer listing counts: `1 missing catch · 1 unreachable state`.
  - Each affected state card gets an amber corner dot with a hover tooltip.
- Zoom controls: fit / 100% / zoom-in / zoom-out (reuse the main graph's zoom composable if sensible, else a local one — Step machines rarely need >3× zoom).
- "Raw ASL" toggle reveals a syntax-highlighted JSON block (reuse the existing code-block component if present, else `<pre>` with tailwind monospace).
- Execution overlay (only when `asl_graph.recent_executions` exists): a small sparkline top-right; hovering a state card shows `24/25 succeeded · avg 180ms`.

`frontend/components/DetailPanel.vue`

- Conditionally render a new "State Machine" section when `node.resource_type === 'aws_sfn_state_machine'`. The section header shows state count and warning count; expanded body embeds `<StateMachineViewer :node="node" />`.
- If screen width > `xl`, offer a "Open full-screen" button that opens the viewer in a modal sized to viewport (`z-50`) — better than AWS console's cramped console pane.

### CLI / config surface

- No new flags for Smart Grouping v2 beyond `.stackmap/groups.yaml`.
- For Step Functions: no new CLI flag. The State Machine panel exposes a `Load recent executions` button that calls AWS only when clicked.
- `stackmap serve` is unaffected — the new data rides inside the same IR JSON.

### Ship checklist

- [x] `stackmap/parsers/asl.py` with full contract coverage; golden-file tests in `tests/parsers/test_asl.py` covering: Lambda Task, `.sync:2`, Choice, Parallel, Map (both classic and Distributed), Catch cascade, unreachable state, missing terminal.
- [x] Terraform parser stores `asl_graph` and emits kind-labeled edges.
- [x] CFN / SAM parsers plumb `DefinitionString` / `DefinitionUri` into `parse_asl`.
- [x] Live scanner persists `asl_graph`; on-demand execution history overlay button.
- [x] `types/asl.ts` + store getter `getAslGraph`.
- [x] `StateMachineViewer.vue` (new) renders all state types + warnings + raw ASL toggle.
- [x] `DetailPanel.vue` conditional section + full-screen modal button.
- [x] Main canvas workflow graph mode opens from **Open workflow graph** and renders ASL states/paths with StackMap nodes and edges.
- [x] Workflow mode no longer uses architecture layers; it uses a dedicated Step Functions flow layout.
- [x] Step state nodes use dedicated icons for Pass, Choice, Task, Map, Parallel, Wait, Succeed, and Fail.
- [x] Older stacked-card Step Functions viewer removed from the active UI.
- [x] **Show target resources** toggle renders mirrored Task targets and jumps back to the real architecture node.
- [x] `/api/sfn-execution-history` loads one selected execution and overlays per-state status.
- [x] Permission warnings document `states:ListExecutions` and `states:GetExecutionHistory`; `stackmap aws-policy --addon stepfunctions` emits the optional policy.
- [x] Clicking a resolved Task resource refocuses the main graph on that node.
- [x] Fixture test: open sample `asl-order-saga.json` fixture → viewer renders 11 states, 2 parallel branches, 1 map, 2 choices, zero warnings.
- [x] Fixture test: open sample `asl-broken.json` → viewer renders warnings banner and amber dots on 3 states.
- [x] Docs: `docs/step-functions.md` with annotated screenshot showing the improvement over the AWS console.

---

## Suggested build order

1. `parse_asl` (pure function + tests) — unblocks everything else, zero UI risk.
2. Terraform integration of `parse_asl` — exercises the contract with real fixtures already in the repo.
3. `StateMachineViewer.vue` MVP against fixture IRs — lands the user-visible win fast.
4. CFN/SAM + live scanner plumbing — uniform support everywhere.
5. Smart Grouping v2 backend strategies — additive, safe to land behind `AutoDetectConfig` defaults.
6. Smart Grouping v2 UI (reason captions, confidence pip, hierarchy filters).
7. Execution history overlay — last because it depends on scanner changes and is the lowest-value slice.

## Out of scope (flag for later)

- Running / triggering Step Functions executions from the StackMap UI.
- Editing ASL inside StackMap.
- Cross-account Step Functions resolution — current resolver works inside one IR; a second pass for org scans can come with the wider org work.
- User-reorderable smart groups (drag-and-drop across the hierarchy).
