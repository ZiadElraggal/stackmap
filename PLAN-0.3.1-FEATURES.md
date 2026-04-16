# StackMap 0.3.1+ Feature Plan

Scope covers the feature roadmap requested after the 0.3.1 foundation work (rebuild, boto3 fix, UI declutter). Each section has: user story, data contract, backend surface, frontend surface, and ship-checklist.

The plan assumes the 0.3.1 foundation is in place:
- Packaged `stackmap/webapp/static/` is rebuilt in CI (and gitignored going forward — TODO)
- PyInstaller bundles boto3/botocore
- `STACKMAP_DEV_FRONTEND=1` is the only way to hit the dev frontend in development
- AWS session failures surface as red errors instead of silent disabling
- `InsightsDock` consolidates Cost / Logs / Drift / Findings toggles in a single top-right rail
- FilterSidebar no longer carries duplicated insight toggles

---

## 1. Diff / Time-Travel UI

**User story.** "I scanned prod yesterday and today — show me what changed. Let me scrub a slider to see the graph at any saved point."

**Data contract.**
Extend the existing IR so the browser receives a `timeline` object:

```jsonc
{
  "timeline": {
    "snapshots": [
      { "id": "2026-04-12T08:00Z", "label": "yesterday", "source": "terraform.tfstate", "graph": { /* full IR */ } },
      { "id": "2026-04-16T08:00Z", "label": "now",       "source": "terraform.tfstate", "graph": { /* full IR */ } }
    ],
    "diffs": [
      { "from": "2026-04-12T08:00Z", "to": "2026-04-16T08:00Z", "added": [...], "removed": [...], "changed": [...] }
    ]
  }
}
```

Reuse `stackmap/graph/diff.py` — it already produces added/removed/changed edges and nodes. The `tests/fixtures/timeline-*.json` fixtures imply the shape is already partly agreed.

**Backend.**
- New CLI: `stackmap timeline --history <dir>` — points at a directory of dated scans and emits a merged IR with `timeline.snapshots` + precomputed `timeline.diffs`.
- `scan` / `scan-aws` / `scan-repo` gain `--snapshot-dir <dir>`: when set, the scan output is also written as `<dir>/<ISO8601>.json` and `stackmap timeline` auto-picks up the history.
- `serve` grows a `/api/timeline` endpoint that re-emits snapshot metadata and returns a specific snapshot's graph on `?id=<snapshot-id>`.

**Frontend.**
- `TimeTravelSlider.vue` already exists — wire it to the new timeline data. Store gets `snapshotId`, `activeSnapshot`, `priorSnapshot`.
- When a snapshot is selected, the graph store swaps its `nodes`/`edges` to that snapshot's view and overlays diff badges:
  - **added** nodes: green dashed pulse ring
  - **removed** nodes: red dashed ghost (still positioned, 40% opacity)
  - **changed** nodes: amber dot on the badge
- New `DiffLegend.vue` floating bottom-center when diffs are active.
- `CommandPalette` gets "Jump to change" entries pulling from `timeline.diffs[last].changed`.

**How it works for users.**
1. `stackmap scan --snapshot-dir .stackmap/history` after each apply — dated JSON accumulates.
2. `stackmap serve --source .stackmap/history` (directory mode) — CLI detects a timeline dir and serves the merged file.
3. User opens the UI → bottom slider shows dots for each snapshot → dragging the scrubber animates the graph. A "Compare with…" split button picks any two snapshots and paints the diff.
4. Presentation mode hides the slider by default.

**Ship checklist.**
- [ ] Extend `StackMapIR` with `timeline: Timeline | None`
- [ ] `timeline` CLI + `--snapshot-dir` flag on existing scanners
- [ ] `/api/timeline` handlers
- [ ] Store `loadTimeline()` / `setActiveSnapshot(id)` / `getDiffBetween(a, b)`
- [ ] `TimeTravelSlider` wired, `DiffLegend.vue` added
- [ ] Graph rendering reacts to `snapshotDiff` (added/removed/changed classes on `GraphNode`/`GraphEdge`)
- [ ] Fixture-based tests against `timeline-before.json` / `timeline-after.json`

---

## 2. Security Findings Overlay

**User story.** "Flag public S3 buckets, 0.0.0.0/0 security groups, IAM `*:*` policies on my graph — now."

**Data contract.**
Extend existing `findings` shape with explicit severity + remediation fields and a new `security` category:

```jsonc
{
  "findings": [
    {
      "id": "sec-001",
      "pattern_id": "s3.public_bucket",
      "category": "security",
      "severity": "high",
      "title": "Public S3 bucket",
      "description": "Bucket allows unauthenticated public access via ACL/policy.",
      "node_ids": ["aws_s3_bucket.assets"],
      "remediation": "Set `block_public_acls = true` and remove public policy statements."
    }
  ]
}
```

**Backend.**
- New module `stackmap/findings/security.py` with pure functions over `StackMapIR`:
  - `detect_public_s3(ir)` — bucket ACL, `public_access_block`, policy statements with `Principal: "*"`
  - `detect_open_security_groups(ir)` — ingress `0.0.0.0/0` on sensitive ports (22, 3389, 3306, 5432, 6379, 9200)
  - `detect_wildcard_iam(ir)` — IAM policy docs with `Action: "*"` + `Resource: "*"`
  - `detect_unencrypted_storage(ir)` — RDS/EBS without `storage_encrypted`, S3 without SSE
  - `detect_missing_logs(ir)` — CloudTrail/CloudFront/ALB without access logging
- Wire into existing findings runner. Additive, doesn't break the current pattern.

**Frontend.**
- Existing `FindingsPanel.vue` already renders grouped-by-severity findings. Add a color bar per severity (red/amber/yellow) and a remediation accordion.
- New graph overlay: findings toggle in `InsightsDock` gains a submenu for each severity. Enabling a finding filter paints affected nodes with a pulsing severity-colored halo, and thickens connected edges.
- Security tab of the detail panel: when the selected node has findings, render them inline above relationships.

**Ship checklist.**
- [ ] `stackmap/findings/security.py` with 5 detectors
- [ ] Fixture coverage: add `public-s3.tfstate`, `open-sg.tfstate` to `tests/fixtures/`
- [ ] `findings[].remediation` propagated end-to-end
- [ ] `FindingsPanel` severity bars + accordion
- [ ] Node halo overlay (new `severity-halo` class on `GraphNode`)
- [ ] DetailPanel integration
- [ ] `--no-security-findings` CLI flag for users who don't want them

---

## 3. Multi-Account Scan Summary View

**User story.** "I have 5 accounts in scan-aws. Show them side-by-side with shared-resource edges so I can reason about the whole org at once."

**Data contract.**
The scanner already emits accounts. Formalize an `organization` block:

```jsonc
{
  "organization": {
    "id": "o-abc123",
    "accounts": [
      { "id": "111111111111", "name": "prod", "region": "us-east-1" },
      { "id": "222222222222", "name": "staging", "region": "us-east-1" }
    ],
    "cross_account_edges": [
      { "from": "222222222222:aws_iam_role.ci", "to": "111111111111:aws_s3_bucket.artifacts", "kind": "assumeRole" }
    ]
  }
}
```

**Backend.**
- `stackmap scan-aws` with `--accounts <csv>` or `--org-scan` already exists — have it populate `organization.*` instead of only producing a flat account list.
- Cross-account detection pass: resolve IAM role trust policies, S3 bucket policies, KMS grants, Transit Gateway attachments, VPC peering, Route53 shared hosted zones, Organizations SCPs.

**Frontend.**
- New view mode `'organization'` alongside `'architecture'` / `'components'` / `'raw'`. Store flag `viewMode === 'organization'` triggers the `OrgSummary.vue` component:
  - Top-level: one card per account showing resource counts + cost estimate + drift counts
  - Bottom: a simplified graph of accounts-as-nodes with cross-account edges between them
  - Clicking an account zooms into its sub-graph (reuses existing architecture view scoped to that account)
- `FilterSidebar` gets an "Accounts" section listing accounts with checkboxes to scope the canvas.

**Ship checklist.**
- [ ] Add `StackMapIR.organization` field
- [ ] Cross-account edge detector in `stackmap/aws_live/scanner.py`
- [ ] `'organization'` view mode in store + routing
- [ ] `OrgSummary.vue`
- [ ] Per-account filter state
- [ ] Fixture `tests/fixtures/multi-account.json`

---

## 4. Semantic Zoom / Sub-Tier Layout

**User story.** "At 10% zoom I see 400 nodes of visual noise. Give me clusters when I'm zoomed out, real nodes when I zoom in."

**Approach.**
Three zoom levels drive rendering — existing layout (`frontend/stores/graph.ts` — `layoutMode`/`visibleNodes`) already computes positions; we add a `zoomTier` derived from canvas `transform.k`:

| Tier | Zoom range | What renders                                     |
|------|------------|--------------------------------------------------|
| `overview` | k < 0.35 | One glyph per smart-group, edges aggregated by group pair |
| `mid`      | 0.35 ≤ k < 0.8 | Groups expanded to components; internal edges hidden |
| `detail`   | k ≥ 0.8 | Current full-fidelity rendering                  |

**Backend.**
- Precompute group-level aggregate nodes + edges in the IR so the frontend doesn't redo the work per frame:
  ```jsonc
  { "aggregates": { "groups": [...], "edges_by_group": [...] } }
  ```
- This already happens partially in `stackmap/grouping/engine.py` — expose it via IR.

**Frontend.**
- `Canvas.vue` reads `store.zoomTier`, swaps the node/edge arrays it draws.
- Smooth transitions: fade-in real nodes over 180ms when crossing a tier boundary; inverse for aggregates.
- Minimap always draws `overview` tier for stability.
- Keep a "Lock zoom tier" toggle in the command palette for screenshot/presentation use.

**Ship checklist.**
- [ ] IR `aggregates` field populated by grouping engine
- [ ] `zoomTier` derived state in store
- [ ] `Canvas.vue` tier-aware rendering
- [ ] Minimap uses overview
- [ ] Tests: 500-node synthetic fixture + assert <16ms frame time at each tier

---

## 5. Cost Anomaly Flag

**User story.** "When `--live-billing` is on, show me resources whose actual usage-derived cost is ≥30% above forecast."

**Data contract.**
When live billing is active, `cost.by_node` gains an `anomaly` field:

```jsonc
{
  "cost": {
    "by_node": {
      "aws_rds_instance.appdb": {
        "monthly_estimate": 262.80,   // forecast
        "monthly_actual":   412.55,   // from CloudWatch / Cost Explorer
        "anomaly": { "delta": 149.75, "ratio": 1.57, "severity": "high" }
      }
    }
  }
}
```

**Backend.**
- In `stackmap/cost/billing.py`, after fetching Cost Explorer + CloudWatch metrics, compute per-node actuals and diff against the heuristic forecast.
- Threshold config: default `anomaly.ratio >= 1.3` → low, `>= 1.6` → medium, `>= 2.0` → high.
- Surface in `/api/cost` when `_live_billing_enabled`.

**Frontend.**
- `CostOverlay.vue` top section gains an "Anomalies" chip that expands to the list of high/medium findings.
- Canvas: anomalous nodes get a subtle orange `~` sigil over their icon. Clicking the sigil opens the CostOverlay pre-filtered.
- Integration with findings: anomalies >= medium also materialize as `category: "cost-anomaly"` findings so they show up in the security/findings panel.

**Ship checklist.**
- [ ] `anomaly` field on `NodeCostEstimate`
- [ ] Thresholds configurable via `--anomaly-thresholds low,med,high`
- [ ] CostOverlay Anomalies section
- [ ] Canvas sigil + hover tooltip
- [ ] Dual surfacing in FindingsPanel

---

## 6. Natural-Language Query Bar

**User story.** "Type `show all public resources` or `who depends on appdb` and the graph filters itself."

**Architecture.**
The existing `SearchBar.vue` handles substring/regex. Layer an NL pass on top, running client-side against an LLM endpoint the user configures.

**Backend.**
- New endpoint `POST /api/nl-query` that:
  1. Accepts `{ query: string }`
  2. Calls the user's configured provider (Anthropic by default — see the `claude-api` skill) with the IR schema + the query
  3. Returns `{ filter: { nodeIds: [...], edgeIds: [...], reason: "..." } }`
- Config via env: `STACKMAP_NL_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...`, default model `claude-sonnet-4-6`.
- If no key is present, the endpoint returns `{ error: "not configured" }` and the UI falls back to plain search.

**Frontend.**
- `SearchBar.vue` gains a mode toggle: `text | regex | ai`. In `ai` mode:
  - Enter → fires `/api/nl-query`
  - Response → applies a transient filter (doesn't overwrite user's category/edge filters; composes with them)
  - Shows the model's `reason` under the search bar
- A small indicator when `ai` mode is unavailable (no key configured).

**Security / safety.**
- The IR is sent to the model — document that clearly. Offer `--no-nl-query` flag to disable.
- No write tools; the model never mutates state, only returns a filter descriptor.

**Ship checklist.**
- [ ] `/api/nl-query` handler + provider shim (Anthropic first, add OpenAI/Ollama later)
- [ ] Config discovery in CLI
- [ ] `SearchBar.vue` mode toggle + AI feedback row
- [ ] Docs: how to set `ANTHROPIC_API_KEY`
- [ ] Test: mock provider returns canned filter → UI applies it

---

## 7. Profile Switcher in UI

**User story.** "Let me change AWS profile from the UI without killing the server and re-running."

**Backend.**
- Discover profiles from `~/.aws/config` + `~/.aws/credentials` on startup.
- `GET /api/profiles` → `{ available: ["dev", "prod", "sandbox"], active: "dev" }`
- `POST /api/profiles/activate` `{ profile: "prod" }` → rebuilds `aws_session`, re-checks `_live_logs_enabled` / `_live_billing_enabled` (still require CLI flag), re-scans if `--watch` is on.
- Atomic: on failure, keep the old session. Return `{ ok: bool, error?: string }`.

**Frontend.**
- Tiny "profile" chip next to the mascot in `FilterSidebar` header. Clicking opens a popover listing available profiles with the active one marked.
- Selecting another profile fires `POST /api/profiles/activate`, then re-fetches `/api/live-features` and `/api/graph`.
- Disabled when no `--aws-profile` / `--live-*` flag was provided at CLI start.

**Ship checklist.**
- [ ] Profile discovery helper (`stackmap/aws_live/profiles.py`)
- [ ] `/api/profiles` GET + `/api/profiles/activate` POST
- [ ] UI chip + popover (`ProfileSwitcher.vue`)
- [ ] Store `activeProfile`, `availableProfiles`
- [ ] Error surface matches the new boto3 error styling
- [ ] Guard against activation racing an in-flight logs/cost fetch

---

## Suggested ship order

1. **0.3.1** — foundation + UI declutter (this branch)
2. **0.3.2** — Security findings overlay (smallest feature, immediate value)
3. **0.3.3** — Profile switcher (quality-of-life, trivial scope)
4. **0.4.0** — Diff / time-travel UI (flagship)
5. **0.4.1** — Semantic zoom (unlocks larger diagrams)
6. **0.5.0** — Multi-account organization view
7. **0.5.1** — Cost anomaly (needs `--live-billing` maturity first)
8. **0.6.0** — Natural-language query (last; carries ops cost + support burden)

Each increment is independently releasable and adds to the Insights dock without breaking existing flows.
