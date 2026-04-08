# StackMap v0.3–v0.5 Implementation Plan

> Comprehensive plan covering 5 major features + prior review improvements.
> Designed to be handed to an implementing agent with full context.

---

## Table of Contents

1. [Review Summary (Prior Analysis)](#1-review-summary)
2. [Feature 1: Drift Detection](#2-drift-detection)
3. [Feature 2: Smart Grouping (Semi-Automatic Projects)](#3-smart-grouping)
4. [Feature 3: Dependency Tracing (Impact Analysis)](#4-dependency-tracing)
5. [Feature 4: Suspicious Pattern Detection](#5-suspicious-patterns)
6. [Feature 5: Cost Overlay](#6-cost-overlay)
7. [Shared Infrastructure Changes](#7-shared-infrastructure)
8. [Implementation Order & Dependencies](#8-implementation-order)
9. [File Reference Map](#9-file-reference)

---

## 1. Review Summary

### What's Strong (keep as-is)
- **Terraform parser** (1816 lines, 4-pass, 132 rules) — near-complete
- **CLI UX** (Typer + Rich + animated mascot) — polished
- **Interactive frontend** (Vue 3 / Nuxt / Dagre / D3) — feature-rich
- **IR data model** (`StackMapIR` with nodes, edges, groups, metadata) — clean and extensible
- **CloudFormation + SAM** — solid intrinsic resolution
- **Diff engine** — clean snapshot comparison
- **Test suite** — 129 tests with phased quality gates

### What Needs Improvement (addressed by this plan)
- Relationship inference: no transitive IAM, no managed policies, no VPC endpoints
- No incremental scanning, global service duplication in live scans
- No frontend tests, no cross-platform CI
- Distribution: macOS Homebrew only, no PyPI/Windows/Docker
- UI: no legend, no onboarding, no PNG export, large components need decomposition

### Quick Wins (do before the 5 features)
1. Publish to PyPI (`pip install stackmap`)
2. Add `--profile` flag to `scan-aws`
3. Add legend/help overlay in UI
4. Decompose `Canvas.vue` (1597 lines), `DetailPanel.vue` (1006 lines), `GraphNode.vue` (958 lines)

---

## 2. Drift Detection

**Goal:** Compare IaC definitions (Terraform state / CloudFormation templates) against live AWS state. Output missing resources, extra resources, and misconfigured relationships.

### 2.1 Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│ IaC Source   │────▶│ Normalizer   │────▶│                  │
│ (tfstate/cfn)│     │ (to IR)      │     │  Drift Engine    │
└─────────────┘     └──────────────┘     │  (compare IRs)   │
                                          │                  │
┌─────────────┐     ┌──────────────┐     │  Outputs:        │
│ Live AWS     │────▶│ Normalizer   │────▶│  - DriftReport   │
│ (scan-aws)   │     │ (to IR)      │     │  - DriftIR       │
└─────────────┘     └──────────────┘     └──────────────────┘
```

### 2.2 New Files

#### `stackmap/drift/__init__.py`
```python
from stackmap.drift.engine import compute_drift, DriftReport
```

#### `stackmap/drift/engine.py` (~400 lines)

**Core dataclasses:**
```python
@dataclass
class DriftStatus(str, Enum):
    IN_SYNC = "in_sync"           # exists in both, properties match
    MISSING_IN_LIVE = "missing"   # in IaC but not in AWS
    EXTRA_IN_LIVE = "extra"       # in AWS but not in IaC
    DRIFTED = "drifted"           # exists in both, properties differ
    EDGE_MISSING = "edge_missing" # relationship in IaC not in live
    EDGE_EXTRA = "edge_extra"     # relationship in live not in IaC

@dataclass
class DriftItem:
    resource_id: str
    resource_type: str
    resource_name: str
    status: DriftStatus
    iac_properties: dict | None   # from IaC IR
    live_properties: dict | None  # from live IR
    drifted_fields: dict | None   # {field: {iac: X, live: Y}}
    severity: str                 # "info", "warning", "critical"

@dataclass
class DriftReport:
    iac_source: str
    live_source: str
    scanned_at: str
    items: list[DriftItem]
    edge_drifts: list[DriftItem]
    summary: DriftSummary

@dataclass
class DriftSummary:
    total_iac: int
    total_live: int
    in_sync: int
    missing: int
    extra: int
    drifted: int
    edge_missing: int
    edge_extra: int
```

**Core function:**
```python
def compute_drift(iac_ir: StackMapIR, live_ir: StackMapIR) -> DriftReport:
    """Compare IaC IR against Live IR and produce a drift report."""
```

**Algorithm:**
1. **Normalize node IDs** — IaC uses `module.name.type.index` while live uses `aws:account:region:type:id`. Build a matching index:
   - Primary match: by ARN (both IRs store ARN in `properties.arn`)
   - Secondary match: by resource type + name/identifier (e.g., `function_name`, `bucket`, `table_name`)
   - Tertiary match: by tag `stackmap:iac-id` or `terraform:resource_id` if present
2. **Match nodes** — produce matched pairs, unmatched-IaC (missing), unmatched-live (extra)
3. **Compare matched properties** — reuse and extend `DIFF_PROPERTIES` from `graph/diff.py`; add drift-specific fields:
   ```python
   DRIFT_PROPERTIES = {
       "aws_lambda_function": {"runtime", "memory_size", "timeout", "handler", "environment", "vpc_config"},
       "aws_s3_bucket": {"versioning", "server_side_encryption_configuration", "public_access_block"},
       "aws_security_group": {"ingress", "egress"},
       # ...extend for all major types
   }
   ```
4. **Compare edges** — match by (source_type+name, target_type+name, edge_type)
5. **Classify severity:**
   - `critical`: missing security groups, extra public-facing resources, drifted IAM policies
   - `warning`: config mismatches (runtime, memory), missing monitoring
   - `info`: tag differences, non-functional changes

#### `stackmap/drift/normalizer.py` (~200 lines)

**Purpose:** Normalize both IaC and Live IRs into a common comparison format.

```python
@dataclass
class NormalizedResource:
    canonical_id: str          # ARN or constructed canonical form
    resource_type: str         # normalized (e.g., aws_lambda_function)
    name: str
    properties: dict           # flattened, normalized properties
    relationships: set[tuple]  # (edge_type, target_canonical_id)

def normalize_ir(ir: StackMapIR, source_kind: str) -> dict[str, NormalizedResource]:
    """Convert IR nodes into normalized resources for comparison."""
```

Key normalization rules:
- Strip module prefixes from Terraform IDs
- Map CloudFormation logical IDs to physical resource IDs (from `properties`)
- Normalize property keys (e.g., `MemorySize` in CFN → `memory_size` in Terraform)
- Build canonical IDs from ARNs where available

### 2.3 CLI Command

Add to `stackmap/cli/main.py`:

```python
@app.command()
def drift(
    iac_source: str = typer.Argument(..., help="Path to IaC source (tfstate, CFN template, or StackMap IR JSON)"),
    live_source: str = typer.Option(None, help="Path to live scan JSON. If omitted, runs scan-aws automatically."),
    regions: list[str] = typer.Option(None, help="AWS regions to scan (if auto-scanning)"),
    services: list[str] = typer.Option(None, help="Services to scan (if auto-scanning)"),
    output: str = typer.Option(None, help="Output path for drift report JSON"),
    serve: bool = typer.Option(False, help="Launch UI with drift overlay"),
    format: str = typer.Option("json", help="Output format: json, table, html"),
) -> None:
    """Compare infrastructure-as-code against live AWS state to detect drift."""
```

### 2.4 Frontend Changes

**New UI elements in the existing Canvas/graph view:**

1. **Drift badges on nodes** — add to `GraphNode.vue`:
   - Green check (in_sync), yellow warning (drifted), red X (missing), blue + (extra)
   - On hover: show drifted fields popup

2. **Drift summary bar** — new component `DriftSummaryBar.vue` (~150 lines):
   - Horizontal bar at top: "23 in sync · 3 drifted · 1 missing · 5 extra"
   - Click category to filter view

3. **Drift detail in DetailPanel** — extend `DetailPanel.vue`:
   - When node selected, show side-by-side: IaC value vs. Live value for drifted fields
   - Red strikethrough for IaC value, green for live value (reuse diff styling)

4. **New metadata field in `StackMapNode`** (frontend `stores/graph.ts`):
   ```typescript
   position_hint: {
     // existing fields...
     drift_status?: 'in_sync' | 'missing' | 'extra' | 'drifted'
     drift_fields?: Record<string, { iac: any; live: any }>
     drift_severity?: 'info' | 'warning' | 'critical'
   }
   ```

### 2.5 IR Extension

Add to `StackMapIR.metadata` when drift mode is active:
```python
metadata = {
    "drift_mode": True,
    "drift_summary": { "in_sync": 23, "drifted": 3, "missing": 1, "extra": 5 },
    "iac_source": "main.tfstate",
    "live_scanned_at": "2026-04-07T12:00:00Z",
}
```

Annotate each node's `position_hint` with drift status (same pattern as existing `diff_status`).

### 2.6 Tests

Create `tests/drift/`:
- `test_drift_engine.py` — unit tests for matching, comparison, severity classification
- `test_drift_normalizer.py` — normalization logic per source type
- `test_drift_cli.py` — CLI integration tests

**Fixture strategy:** Create paired fixtures:
- `tests/fixtures/drift-lambda-api.tfstate` (IaC)
- `tests/fixtures/drift-lambda-api-live.json` (simulated live scan with intentional drift)

### 2.7 Implementation Steps

1. Create `stackmap/drift/normalizer.py` — resource normalization
2. Create `stackmap/drift/engine.py` — diff algorithm + dataclasses
3. Add `drift` command to `stackmap/cli/main.py`
4. Add `drift_status` rendering to `GraphNode.vue`
5. Add `DriftSummaryBar.vue` component
6. Extend `DetailPanel.vue` with drift field comparison
7. Add tests + fixtures
8. Add `make drift-check` to Makefile

---

## 3. Smart Grouping (Semi-Automatic Projects)

**Goal:** Let users define grouping rules (tags, naming patterns, VPCs, etc.) and auto-cluster resources into logical projects/services.

### 3.1 Architecture

```
┌───────────────┐     ┌────────────────┐     ┌──────────────┐
│ Grouping Rules│────▶│ Group Engine   │────▶│ StackMapIR   │
│ (.stackmap    │     │ (apply rules   │     │ with new     │
│  rules file)  │     │  to IR nodes)  │     │ smart groups │
└───────────────┘     └────────────────┘     └──────────────┘
```

### 3.2 Grouping Rules Format

**File: `.stackmap/groups.yaml`** (user-defined, lives in project root)

```yaml
version: 1
groups:
  - name: "Auth Service"
    icon: "security"
    color: "#ef4444"
    rules:
      - match: tag
        key: "service"
        value: "auth"
      - match: name
        pattern: "auth-*"
      - match: name
        pattern: "*-cognito-*"

  - name: "Analytics Stack"
    icon: "database"
    color: "#C084FC"
    rules:
      - match: tag
        key: "project"
        value: "analytics"
      - match: type
        pattern: "aws_kinesis_*"
      - match: resource_type
        values: ["aws_glue_catalog_database", "aws_athena_workgroup"]

  - name: "API Layer"
    icon: "integration"
    color: "#FB923C"
    rules:
      - match: tag
        key: "layer"
        value: "api"
      - match: vpc
        id: "vpc-0abc123"    # all resources in this VPC
      - match: subnet
        ids: ["subnet-aaa", "subnet-bbb"]

# Auto-detect rules (applied when no explicit match)
auto_detect:
  enabled: true
  strategies:
    - tag_key: "service"         # group by this tag value
    - tag_key: "project"
    - tag_key: "app"
    - naming_prefix: true        # group by common name prefix
      min_group_size: 3          # need at least 3 resources to form a group
    - vpc_based: true            # one group per VPC
```

### 3.3 New Files

#### `stackmap/grouping/__init__.py`

#### `stackmap/grouping/engine.py` (~350 lines)

```python
@dataclass
class GroupingRule:
    match_type: str       # "tag", "name", "type", "vpc", "subnet", "resource_type"
    key: str | None       # tag key
    value: str | None     # exact value
    pattern: str | None   # glob/regex pattern
    values: list[str] | None  # list of exact values
    ids: list[str] | None     # VPC/subnet IDs

@dataclass
class SmartGroupConfig:
    name: str
    icon: str | None
    color: str | None
    rules: list[GroupingRule]
    group_type: str = "smart_group"

def load_grouping_config(config_path: str | Path) -> list[SmartGroupConfig]:
    """Load .stackmap/groups.yaml and parse into configs."""

def apply_smart_groups(ir: StackMapIR, configs: list[SmartGroupConfig]) -> StackMapIR:
    """Apply grouping rules to IR. Returns new IR with added StackMapGroups."""

def auto_detect_groups(ir: StackMapIR, strategies: dict) -> list[StackMapGroup]:
    """Heuristic grouping when no explicit rules match."""
```

**Auto-detection algorithm:**
1. **Tag-based clustering**: For each configured tag key, group all nodes sharing the same tag value
2. **Naming prefix**: Extract common prefixes (split on `-`, `_`, `.`), cluster if ≥ 3 nodes share a prefix of length ≥ 2 segments
3. **VPC-based**: If node has `vpc_id` in properties or is child of a VPC group, cluster by VPC
4. **Connectivity-based**: Run connected components on the edge graph (excluding `REFERENCES` and `CONTAINS`), each component becomes a candidate group
5. **Merge small groups**: If a group has < 3 nodes and shares edges with another group, merge them

#### `stackmap/grouping/suggest.py` (~150 lines)

```python
def suggest_groups(ir: StackMapIR) -> list[SmartGroupConfig]:
    """Analyze IR and suggest grouping rules the user can accept/modify."""
```

Returns suggestions like:
- "Found 8 resources tagged `service=auth`. Create 'Auth Service' group?"
- "Found 5 resources with name prefix `analytics-`. Create 'Analytics' group?"
- "Found 12 resources in VPC `vpc-abc123`. Create 'Production VPC' group?"

### 3.4 CLI Integration

```python
@app.command()
def suggest_groups(
    source: str = typer.Argument(..., help="Path to IR JSON or IaC source"),
    output: str = typer.Option(".stackmap/groups.yaml", help="Output path for suggested config"),
) -> None:
    """Analyze infrastructure and suggest grouping rules."""

# Also add --groups flag to scan, scan-repo, scan-aws, serve:
# --groups PATH  Path to .stackmap/groups.yaml (auto-detected if in project root)
```

### 3.5 Frontend Changes

1. **New group_type `"smart_group"` rendering** in `GroupBoundary.vue`:
   - Colored boundary box with icon + label
   - Collapsible (click to fold into summary card)
   - Show resource count badge

2. **FilterSidebar.vue** — add "Projects" section:
   - List of smart groups with toggle visibility
   - Expand to see member resources
   - "Suggest groups" button that calls API

3. **New API endpoint** in `main.py` serve handler:
   - `POST /api/suggest-groups` — returns suggested grouping configs
   - `POST /api/apply-groups` — applies rules and returns updated IR

4. **`stores/graph.ts`** — add:
   ```typescript
   smartGroups: StackMapGroup[]  // filtered to group_type === 'smart_group'
   collapsedGroups: Set<string>  // group IDs that are collapsed
   ```

### 3.6 Tests

- `tests/grouping/test_engine.py` — rule matching, auto-detection, merge logic
- `tests/grouping/test_suggest.py` — suggestion quality
- `tests/grouping/test_config.py` — YAML parsing, validation
- Fixture: `tests/fixtures/groups-config.yaml`

### 3.7 Implementation Steps

1. Create `stackmap/grouping/engine.py` — rule matching + auto-detect
2. Create `stackmap/grouping/suggest.py` — suggestion generation
3. Add `suggest-groups` CLI command
4. Add `--groups` flag to `scan`, `scan-repo`, `scan-aws`, `serve`
5. Extend `GroupBoundary.vue` for smart_group rendering
6. Add projects section to `FilterSidebar.vue`
7. Add collapse/expand to `stores/graph.ts` + `Canvas.vue`
8. Tests + fixtures

---

## 4. Dependency Tracing (Impact Analysis)

**Goal:** Click any resource → see upstream dependencies (what it depends on) and downstream impact (what breaks if it fails).

### 4.1 Architecture

This is primarily a **graph traversal feature** built on the existing IR edges.

```
Click Lambda ──▶ Trace upstream:  API Gateway → Route53 → CloudFront
               ──▶ Trace downstream: DynamoDB, SQS, SNS, S3
               ──▶ Blast radius: all transitively dependent resources
```

### 4.2 New Files

#### `stackmap/graph/trace.py` (~250 lines)

```python
@dataclass
class TraceResult:
    origin_id: str
    upstream: list[TraceHop]     # resources this depends on
    downstream: list[TraceHop]   # resources that depend on this
    blast_radius: int            # total downstream count
    critical_path: list[str]     # longest dependency chain

@dataclass
class TraceHop:
    node_id: str
    depth: int                   # hops from origin
    edge_type: str               # how connected
    edge_label: str
    direction: str               # "upstream" | "downstream"

def trace_dependencies(
    ir: StackMapIR,
    origin_id: str,
    max_depth: int = 10,
    include_edge_types: set[str] | None = None,
    exclude_edge_types: set[str] | None = None,
) -> TraceResult:
    """BFS/DFS traversal from origin node in both directions."""
```

**Algorithm:**
1. Build adjacency lists: `forward_adj[source]` = list of (target, edge) and `reverse_adj[target]` = list of (source, edge)
2. **Upstream trace**: BFS on `reverse_adj` from origin, excluding `CONTAINS` edges
3. **Downstream trace**: BFS on `forward_adj` from origin, excluding `CONTAINS` edges
4. **Blast radius**: count of unique nodes in downstream trace
5. **Critical path**: longest path in downstream DAG (topological sort + longest path)

**Edge direction semantics for tracing:**
- `TRIGGERS`: source triggers target → downstream
- `READS_FROM`: source reads from target → target is upstream data dependency
- `WRITES_TO`: source writes to target → target is downstream data sink
- `ROUTES_TO`: source routes to target → target is downstream
- `AUTHENTICATES`: source authenticates with target → target is upstream auth dependency
- `CROSS_ACCOUNT_REFERENCE`: bidirectional consideration
- `REFERENCES`: weak link, include at depth 1 only
- `CONTAINS`: skip (structural, not functional)

### 4.3 CLI Command

```python
@app.command()
def trace(
    source: str = typer.Argument(..., help="Path to IR JSON"),
    resource: str = typer.Argument(..., help="Resource ID or name to trace"),
    direction: str = typer.Option("both", help="upstream, downstream, or both"),
    max_depth: int = typer.Option(5, help="Maximum trace depth"),
    output: str = typer.Option(None, help="Output path for trace result JSON"),
) -> None:
    """Trace upstream dependencies and downstream impact of a resource."""
```

**Terminal output** (Rich tree):
```
🔍 Tracing: process-payment (aws_lambda_function)

⬆ UPSTREAM (what it depends on):
  ├── api-gateway (aws_api_gateway_rest_api) ── triggers
  │   └── cloudfront-cdn (aws_cloudfront_distribution) ── routes to
  │       └── api.example.com (aws_route53_record) ── routes to
  └── payment-role (aws_iam_role) ── authenticates

⬇ DOWNSTREAM (what breaks if it fails):
  ├── orders-table (aws_dynamodb_table) ── writes to
  │   └── analytics-stream (aws_kinesis_stream) ── triggers
  ├── receipts-bucket (aws_s3_bucket) ── writes to
  └── notification-topic (aws_sns_topic) ── writes to
      └── email-queue (aws_sqs_queue) ── triggers

💥 Blast radius: 5 resources affected
🔗 Critical path: 3 hops (process-payment → orders-table → analytics-stream)
```

### 4.4 Frontend Changes

**This is the most impactful UI feature.** Two modes:

#### Mode 1: Hover Trace (lightweight)
- On node hover (after 500ms delay), dim all nodes NOT in 1-hop upstream/downstream
- Highlight upstream edges in blue, downstream in orange
- Show badge: "↑3 ↓5" (upstream/downstream counts)

#### Mode 2: Click Trace (full analysis)
- Click node → DetailPanel shows "Dependencies" tab
- Upstream/downstream tree rendered as collapsible list
- "Highlight" button dims all non-related nodes
- "Isolate" button hides all non-related nodes
- Blast radius counter with severity coloring

**Implementation in `stores/graph.ts`:**
```typescript
// New state
traceResult: TraceResult | null
traceOriginId: string | null

// New action
async traceNode(nodeId: string): Promise<void> {
  // If served: fetch from /api/trace?node={nodeId}
  // If static HTML: compute client-side (include trace.ts in frontend)
}
```

**New file: `frontend/composables/useTrace.ts`** (~120 lines)
- Client-side BFS implementation (so it works in exported HTML too)
- Reuses existing edge data from store

**Changes to `Canvas.vue`:**
- When `traceResult` is set, apply opacity: 0.08 to non-traced nodes
- Highlight traced edges with animated flow dots (reuse existing animation)
- Color code: blue glow for upstream, orange glow for downstream

**Changes to `DetailPanel.vue`:**
- Add "Dependencies" tab (alongside existing info)
- Upstream tree + downstream tree
- Blast radius stat card

### 4.5 API Endpoint

Add to serve handler in `main.py`:
```python
# GET /api/trace?node={nodeId}&depth={maxDepth}&direction={both|upstream|downstream}
```

### 4.6 Tests

- `tests/graph/test_trace.py` — BFS traversal, direction semantics, depth limiting, blast radius
- Use existing fixtures (`simple-lambda-api.tfstate` → parse → trace Lambda)

### 4.7 Implementation Steps

1. Create `stackmap/graph/trace.py` — core traversal algorithm
2. Add `trace` CLI command to `main.py`
3. Add `/api/trace` endpoint to serve handler
4. Create `frontend/composables/useTrace.ts` — client-side BFS
5. Add trace state to `stores/graph.ts`
6. Add trace visualization to `Canvas.vue` (opacity + glow)
7. Add Dependencies tab to `DetailPanel.vue`
8. Tests

---

## 5. Suspicious Pattern Detection

**Goal:** Flag orphaned resources, unused infrastructure, weird cross-region links, and basic public exposure without becoming a security scanner.

### 5.1 Architecture

```
┌──────────┐     ┌──────────────┐     ┌────────────────┐
│StackMapIR│────▶│ Pattern Rules│────▶│ Findings List  │
│          │     │ (analyzers)  │     │ + Annotations  │
└──────────┘     └──────────────┘     └────────────────┘
```

### 5.2 New Files

#### `stackmap/analysis/__init__.py`

#### `stackmap/analysis/patterns.py` (~400 lines)

```python
class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Finding:
    id: str                    # unique finding ID
    pattern_id: str            # e.g., "orphaned-resource", "public-s3"
    title: str                 # human-readable
    description: str           # detailed explanation
    severity: Severity
    node_ids: list[str]        # affected resources
    recommendation: str        # what to do
    category: str              # "orphan", "unused", "exposure", "cross-region", "cost"

def analyze_patterns(ir: StackMapIR) -> list[Finding]:
    """Run all pattern detectors on the IR."""
    findings = []
    findings.extend(_detect_orphaned_resources(ir))
    findings.extend(_detect_unused_load_balancers(ir))
    findings.extend(_detect_cross_region_links(ir))
    findings.extend(_detect_public_exposure(ir))
    findings.extend(_detect_unencrypted_storage(ir))
    findings.extend(_detect_oversized_resources(ir))
    findings.extend(_detect_missing_monitoring(ir))
    return findings
```

**Pattern Detectors:**

1. **Orphaned Resources** (`_detect_orphaned_resources`):
   - Resources with 0 edges (not source or target of any edge)
   - Exclude helper types (IAM policies, log groups — they're expected to be leaf nodes)
   - Flag: "This {resource_type} has no connections to any other resource"

2. **Unused Load Balancers** (`_detect_unused_load_balancers`):
   - ALB/NLB/CLB with no `ROUTES_TO` target edges
   - Or target groups with 0 registered targets (check `properties`)
   - Flag: "Load balancer has no active targets"

3. **Cross-Region Links** (`_detect_cross_region_links`):
   - Edges where source.metadata.region != target.metadata.region
   - Exclude expected patterns: CloudFront→S3, Route53→anything (these are global)
   - Flag: "Unexpected cross-region link: {source_region} → {target_region}"

4. **Public Exposure** (`_detect_public_exposure`):
   - S3 buckets with `acl: "public-read"` or no `public_access_block`
   - Security groups with ingress `0.0.0.0/0` on non-443/80 ports
   - RDS instances with `publicly_accessible: true`
   - Lambda with no VPC config that writes to public resources
   - Flag: "Resource may be publicly accessible"

5. **Unencrypted Storage** (`_detect_unencrypted_storage`):
   - S3 without `server_side_encryption_configuration`
   - RDS without `storage_encrypted: true`
   - DynamoDB without point-in-time recovery
   - Flag: "Storage resource has no encryption configured"

6. **Oversized Resources** (`_detect_oversized_resources`):
   - Lambda with `memory_size > 3008` and `timeout < 10`
   - RDS `instance_class` in expensive tier list (`db.r6g.16xlarge`, etc.)
   - Flag: "Resource may be over-provisioned"

7. **Missing Monitoring** (`_detect_missing_monitoring`):
   - Lambda functions without a corresponding CloudWatch log group
   - ECS services without CloudWatch alarms
   - Flag: "No monitoring detected for this resource"

### 5.3 CLI Command

```python
@app.command()
def analyze(
    source: str = typer.Argument(..., help="Path to IR JSON or IaC source"),
    patterns: list[str] = typer.Option(None, help="Specific patterns to check (default: all)"),
    severity: str = typer.Option("info", help="Minimum severity: info, warning, critical"),
    output: str = typer.Option(None, help="Output path for findings JSON"),
    format: str = typer.Option("table", help="Output format: table, json"),
) -> None:
    """Detect suspicious patterns and potential issues in infrastructure."""
```

**Terminal output** (Rich table):
```
┌──────────┬───────────┬──────────────────────────────────────┬──────────┐
│ Severity │ Pattern   │ Finding                              │ Resource │
├──────────┼───────────┼──────────────────────────────────────┼──────────┤
│ ⚠ WARN   │ orphaned  │ S3 bucket has no connections         │ logs-bkt │
│ 🔴 CRIT  │ exposure  │ Security group allows 0.0.0.0/0:22  │ sg-web   │
│ ℹ INFO   │ x-region  │ Unexpected us-east-1 → eu-west-1    │ lambda-a │
│ ⚠ WARN   │ unused-lb │ ALB has no active targets            │ alb-old  │
└──────────┴───────────┴──────────────────────────────────────┴──────────┘
4 findings (1 critical, 2 warnings, 1 info)
```

### 5.4 Frontend Changes

1. **Findings panel** — new tab in `FilterSidebar.vue`:
   - List of findings grouped by severity
   - Click finding → highlight affected nodes
   - Badge count on sidebar tab: "4 findings"

2. **Node annotations** — extend `GraphNode.vue`:
   - Small warning triangle badge on affected nodes
   - Color matches severity (red/yellow/blue)
   - Hover shows finding summary

3. **IR metadata extension:**
   ```python
   metadata["findings"] = [finding.to_dict() for finding in findings]
   ```

4. **Store extension** (`stores/graph.ts`):
   ```typescript
   findings: Finding[]
   activeFindingFilter: string | null  // pattern_id to highlight
   ```

### 5.5 Tests

- `tests/analysis/test_patterns.py` — each detector with positive and negative cases
- Create fixtures with intentional issues:
  - `tests/fixtures/suspicious-infra.json` — IR with orphans, public S3, cross-region links

### 5.6 Implementation Steps

1. Create `stackmap/analysis/patterns.py` — all 7 detectors
2. Add `analyze` CLI command
3. Add findings to IR metadata in scan/scan-repo/scan-aws pipelines (optional flag `--analyze`)
4. Add findings panel to `FilterSidebar.vue`
5. Add warning badges to `GraphNode.vue`
6. Tests + fixtures

---

## 6. Cost Overlay

**Goal:** Show estimated cost per node, per group, per tier. Highlight expensive paths.

### 6.1 Architecture

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐
│StackMapIR│────▶│ Cost Estimator│────▶│ IR with cost │
│          │     │ (pricing DB)  │     │ annotations  │
└──────────┘     └───────────────┘     └──────────────┘
                       │
                 ┌─────┴──────┐
                 │ Pricing DB │  (embedded JSON or AWS Pricing API)
                 └────────────┘
```

### 6.2 Pricing Strategy

**Approach: Embedded pricing database** (not AWS Pricing API — too slow, requires auth).

Create a static pricing JSON file updated periodically:

#### `stackmap/cost/pricing_db.json` (~2000 lines)

Structure:
```json
{
  "version": "2026-04",
  "currency": "USD",
  "services": {
    "aws_lambda_function": {
      "pricing_model": "invocation",
      "base_monthly": 0,
      "notes": "Cost depends on invocations + duration. Estimate based on memory.",
      "tiers": {
        "128": 0.50,
        "256": 1.00,
        "512": 2.50,
        "1024": 5.00,
        "2048": 12.00,
        "3008": 20.00,
        "10240": 65.00
      },
      "estimate_key": "memory_size",
      "estimate_note": "Estimated monthly cost at ~1M invocations/month, 200ms avg"
    },
    "aws_dynamodb_table": {
      "pricing_model": "capacity",
      "on_demand_base": 1.25,
      "provisioned_read_per_rcu": 0.00065,
      "provisioned_write_per_wcu": 0.00065,
      "estimate_key": "billing_mode"
    },
    "aws_db_instance": {
      "pricing_model": "instance",
      "instance_costs": {
        "db.t3.micro": 12.41,
        "db.t3.small": 24.82,
        "db.t3.medium": 49.64,
        "db.r6g.large": 131.40,
        "db.r6g.xlarge": 262.80
      },
      "estimate_key": "instance_class",
      "multi_az_multiplier": 2.0
    },
    "aws_s3_bucket": {
      "pricing_model": "storage",
      "per_gb_monthly": 0.023,
      "base_monthly": 0,
      "notes": "Estimate assumes 100GB standard storage"
    }
    // ... more services
  }
}
```

### 6.3 New Files

#### `stackmap/cost/__init__.py`

#### `stackmap/cost/estimator.py` (~300 lines)

```python
@dataclass
class CostEstimate:
    resource_id: str
    monthly_estimate: float       # USD/month
    confidence: str               # "high", "medium", "low", "unknown"
    pricing_model: str            # "instance", "invocation", "storage", etc.
    estimate_note: str            # human-readable basis
    breakdown: dict | None        # optional line items

@dataclass
class CostReport:
    total_monthly: float
    by_node: dict[str, CostEstimate]
    by_group: dict[str, float]         # group_id → total
    by_category: dict[str, float]      # ResourceCategory → total
    by_tier: dict[str, float]          # tier → total
    expensive_paths: list[dict]        # top 5 most expensive source→target paths
    currency: str

def estimate_costs(ir: StackMapIR) -> CostReport:
    """Estimate costs for all resources in the IR."""

def _estimate_node_cost(node: StackMapNode, pricing_db: dict) -> CostEstimate:
    """Estimate cost for a single node based on its resource_type and properties."""
```

**Estimation logic per service:**
- **Lambda**: Look up `memory_size` in tier table. Default to 256MB estimate.
- **DynamoDB**: Check `billing_mode` (PAY_PER_REQUEST vs PROVISIONED). For provisioned, use RCU/WCU from properties.
- **RDS**: Look up `instance_class` in pricing table. Apply `multi_az` multiplier.
- **ECS**: Fargate pricing from `cpu` + `memory` in task definition. EC2-backed: estimate from instance type.
- **S3**: Base estimate (configurable, default 100GB). Multiply by per-GB rate.
- **CloudFront**: Base estimate per distribution (~$50/month typical).
- **NAT Gateway**: $32.40/month + data processing estimate.
- **ALB/NLB**: $16.20/month base + LCU estimate.
- **ElastiCache**: Instance type lookup similar to RDS.
- **SQS/SNS**: Minimal base ($0-5/month) unless high volume indicated.

**Confidence levels:**
- `high`: instance type or exact config known (RDS, ElastiCache)
- `medium`: usage-dependent but properties give good hint (Lambda memory, DynamoDB mode)
- `low`: usage-dependent with no hint (S3 size, CloudFront traffic)
- `unknown`: no pricing data for this resource type

**Expensive path detection:**
```python
def _find_expensive_paths(ir: StackMapIR, costs: dict[str, CostEstimate]) -> list[dict]:
    """Find the top 5 most expensive connected paths through the graph."""
    # Walk each edge, sum source + target cost. Rank by total.
    # For chains: trace from most expensive node downstream, sum path.
```

### 6.4 CLI Integration

```python
# Add --cost flag to scan, scan-repo, scan-aws:
@app.command()
def scan(
    # ... existing params ...
    cost: bool = typer.Option(False, "--cost", help="Include cost estimates in output"),
):
```

Also add standalone command:
```python
@app.command()
def cost(
    source: str = typer.Argument(..., help="Path to IR JSON"),
    output: str = typer.Option(None, help="Output path for cost report JSON"),
    format: str = typer.Option("table", help="Output format: table, json"),
) -> None:
    """Estimate monthly costs for infrastructure resources."""
```

**Terminal output:**
```
💰 Monthly Cost Estimate

 Tier         │ Cost/mo
──────────────┼─────────
 data         │ $487.20
 compute      │ $312.00
 serverless   │ $45.00
 api          │ $16.20
 frontend     │ $50.00
──────────────┼─────────
 TOTAL        │ $910.40

Top expensive resources:
 1. prod-db (aws_db_instance, db.r6g.xlarge) ── $262.80/mo
 2. cache-cluster (aws_elasticache_replication_group) ── $131.40/mo
 3. nat-gateway-1 (aws_nat_gateway) ── $32.40/mo

Confidence: 12 high, 8 medium, 5 low, 3 unknown
```

### 6.5 Frontend Changes

**This is the most visually impactful feature.**

1. **Cost toggle button** — add to EditToolbar or FilterSidebar:
   - Toggle "Show costs" on/off
   - When on: node sizes scale by cost, cost labels appear

2. **Node cost labels** — extend `GraphNode.vue`:
   - Small badge below node: `$262/mo`
   - Color gradient: green ($0-10) → yellow ($10-100) → orange ($100-500) → red ($500+)
   - Size scaling: expensive nodes get 10-20% larger

3. **Group cost summaries** — extend `GroupBoundary.vue`:
   - Total cost label in group header: "Auth Service — $145/mo"

4. **Tier cost bar** — new element in `Canvas.vue` tier bands:
   - Right-aligned cost total per tier: "data tier — $487/mo"

5. **Cost heatmap mode** — new view mode option:
   - All nodes colored by cost (green→red gradient)
   - Edge thickness proportional to connected cost

6. **Cost detail in DetailPanel** — when node selected:
   - Monthly estimate with confidence indicator
   - Pricing model explanation
   - Breakdown (if available)

7. **Store extension** (`stores/graph.ts`):
   ```typescript
   costData: CostReport | null
   showCosts: boolean
   costHeatmap: boolean
   ```

8. **IR metadata extension:**
   ```python
   # Each node's position_hint gets:
   position_hint["cost_monthly"] = 262.80
   position_hint["cost_confidence"] = "high"
   position_hint["cost_note"] = "db.r6g.xlarge, multi-AZ"

   # IR metadata gets:
   metadata["cost_summary"] = {
       "total_monthly": 910.40,
       "by_tier": {...},
       "by_category": {...},
       "currency": "USD"
   }
   ```

### 6.6 Tests

- `tests/cost/test_estimator.py` — per-service estimation, confidence, expensive paths
- `tests/cost/test_pricing_db.py` — pricing DB schema validation
- Use existing fixtures + verify cost annotations

### 6.7 Implementation Steps

1. Create `stackmap/cost/pricing_db.json` — embedded pricing data
2. Create `stackmap/cost/estimator.py` — estimation engine
3. Add `cost` CLI command + `--cost` flag to scan commands
4. Add cost annotations to IR pipeline
5. Add cost toggle + labels to frontend (`GraphNode.vue`, `FilterSidebar.vue`)
6. Add cost heatmap mode
7. Add cost detail to `DetailPanel.vue`
8. Tests

---

## 7. Shared Infrastructure Changes

These changes support multiple features and should be done first.

### 7.1 IR Model Extensions (`stackmap/parsers/base.py`)

Add new EdgeType values:
```python
class EdgeType(str, Enum):
    # ... existing ...
    DEPENDS_ON = "depends_on"    # for drift/trace
```

Extend `StackMapNode` with optional annotation fields (via `position_hint` and `metadata` — no schema change needed, just documented conventions):

| Field | Location | Used By |
|-------|----------|---------|
| `drift_status` | `position_hint` | Drift Detection |
| `drift_fields` | `position_hint` | Drift Detection |
| `cost_monthly` | `position_hint` | Cost Overlay |
| `cost_confidence` | `position_hint` | Cost Overlay |
| `smart_group` | `metadata` | Smart Grouping |
| `findings` | `metadata` | Pattern Detection |

### 7.2 API Endpoints (`stackmap/cli/main.py`)

Add to the serve handler's request processing:

| Endpoint | Method | Feature |
|----------|--------|---------|
| `/api/trace` | GET | Dependency Tracing |
| `/api/drift` | GET | Drift Detection |
| `/api/findings` | GET | Pattern Detection |
| `/api/cost` | GET | Cost Overlay |
| `/api/suggest-groups` | POST | Smart Grouping |
| `/api/apply-groups` | POST | Smart Grouping |

### 7.3 Frontend Store Extension (`stores/graph.ts`)

```typescript
// Add to store state
interface StackMapStoreState {
  // ... existing ...

  // Feature: Drift
  driftMode: boolean
  driftSummary: DriftSummary | null

  // Feature: Smart Groups
  smartGroups: StackMapGroup[]
  collapsedGroups: Set<string>

  // Feature: Trace
  traceResult: TraceResult | null
  traceOriginId: string | null

  // Feature: Findings
  findings: Finding[]
  activeFindingFilter: string | null

  // Feature: Cost
  costData: CostReport | null
  showCosts: boolean
}
```

### 7.4 New Makefile Targets

```makefile
drift-check:
	pytest tests/drift/ -v

grouping-check:
	pytest tests/grouping/ -v

trace-check:
	pytest tests/graph/test_trace.py -v

analysis-check:
	pytest tests/analysis/ -v

cost-check:
	pytest tests/cost/ -v

phase5-check: phase4-check drift-check grouping-check trace-check analysis-check cost-check
	@echo "Phase 5: All advanced features passing"
```

---

## 8. Implementation Order & Dependencies

```
Week 1-2: Shared Infrastructure (§7)
    ├── IR model conventions documented
    ├── API endpoint scaffolding
    └── Frontend store structure

Week 2-3: Dependency Tracing (§4)          ◄── Least dependencies, highest UI impact
    ├── graph/trace.py
    ├── useTrace.ts composable
    ├── Canvas + DetailPanel integration
    └── Tests

Week 3-5: Drift Detection (§2)             ◄── Builds on existing diff engine
    ├── drift/normalizer.py
    ├── drift/engine.py
    ├── CLI command
    ├── Frontend drift badges + panel
    └── Tests

Week 5-6: Suspicious Pattern Detection (§5) ◄── Lightweight, standalone
    ├── analysis/patterns.py
    ├── CLI command
    ├── Findings panel in sidebar
    └── Tests

Week 6-7: Smart Grouping (§3)              ◄── Needs pattern detection insights
    ├── grouping/engine.py + suggest.py
    ├── groups.yaml format
    ├── CLI + --groups flag
    ├── GroupBoundary + FilterSidebar
    └── Tests

Week 7-9: Cost Overlay (§6)                ◄── Most complex frontend work
    ├── cost/pricing_db.json
    ├── cost/estimator.py
    ├── CLI + --cost flag
    ├── Full frontend integration
    └── Tests

Week 9-10: Integration & Polish
    ├── Cross-feature interactions
    ├── Performance testing at scale
    ├── Documentation updates
    └── Release prep
```

**Dependency graph:**
```
Shared Infra ──▶ Dep Tracing ──▶ (independent)
             ──▶ Drift Detection ──▶ (independent)
             ──▶ Pattern Detection ──▶ Smart Grouping (can use findings)
             ──▶ Cost Overlay (independent, but pairs with Pattern Detection for "cost" findings)
```

---

## 9. File Reference Map

### New directories to create:
```
stackmap/
├── drift/
│   ├── __init__.py
│   ├── engine.py          # ~400 lines
│   └── normalizer.py      # ~200 lines
├── grouping/
│   ├── __init__.py
│   ├── engine.py          # ~350 lines
│   └── suggest.py         # ~150 lines
├── analysis/
│   ├── __init__.py
│   └── patterns.py        # ~400 lines
├── cost/
│   ├── __init__.py
│   ├── estimator.py       # ~300 lines
│   └── pricing_db.json    # ~2000 lines
└── graph/
    ├── diff.py            # existing
    └── trace.py           # ~250 lines (NEW)

frontend/
├── composables/
│   ├── useLayout.ts       # existing
│   ├── useGraph.ts        # existing
│   └── useTrace.ts        # ~120 lines (NEW)
└── components/
    ├── DriftSummaryBar.vue    # ~150 lines (NEW)
    ├── FindingsPanel.vue      # ~200 lines (NEW)
    ├── CostOverlay.vue        # ~180 lines (NEW)
    └── TracePanel.vue         # ~200 lines (NEW)

tests/
├── drift/
│   ├── test_drift_engine.py
│   ├── test_drift_normalizer.py
│   └── test_drift_cli.py
├── grouping/
│   ├── test_engine.py
│   ├── test_suggest.py
│   └── test_config.py
├── analysis/
│   └── test_patterns.py
├── cost/
│   ├── test_estimator.py
│   └── test_pricing_db.py
└── graph/
    ├── test_diff.py       # existing
    └── test_trace.py      # NEW
```

### Existing files to modify:
| File | Changes |
|------|---------|
| `stackmap/cli/main.py` | Add 4 new commands: `drift`, `trace`, `analyze`, `cost`. Add `--cost`, `--analyze`, `--groups` flags to `scan`/`scan-repo`/`scan-aws`. Add 6 API endpoints to serve handler. |
| `stackmap/parsers/base.py` | Document annotation conventions in docstrings. No schema changes needed. |
| `frontend/stores/graph.ts` | Add state for drift, trace, findings, cost, smart groups. Add actions/getters. |
| `frontend/components/Canvas.vue` | Add trace opacity dimming, cost heatmap mode, drift badge rendering. |
| `frontend/components/GraphNode.vue` | Add cost label, drift badge, finding warning triangle, trace glow. |
| `frontend/components/DetailPanel.vue` | Add Dependencies tab, Drift tab, Cost section, Findings section. |
| `frontend/components/FilterSidebar.vue` | Add Findings panel, Projects (smart groups) section, Cost toggle. |
| `frontend/components/GroupBoundary.vue` | Add smart_group rendering with colors/icons, cost totals. |
| `frontend/components/EditToolbar.vue` | Add cost toggle, trace mode toggle. |
| `Makefile` | Add phase5-check and per-feature check targets. |
| `pyproject.toml` | Bump version, add PyYAML dependency (already present). |

### Estimated total new code:
| Feature | Backend | Frontend | Tests | Total |
|---------|---------|----------|-------|-------|
| Dependency Tracing | ~250 lines | ~500 lines | ~200 lines | ~950 |
| Drift Detection | ~600 lines | ~500 lines | ~300 lines | ~1400 |
| Pattern Detection | ~400 lines | ~350 lines | ~250 lines | ~1000 |
| Smart Grouping | ~500 lines | ~400 lines | ~250 lines | ~1150 |
| Cost Overlay | ~300 lines + 2000 JSON | ~600 lines | ~200 lines | ~3100 |
| **Total** | **~4050 lines** | **~2350 lines** | **~1200 lines** | **~7600** |
