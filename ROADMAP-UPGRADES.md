# StackMap Roadmap Upgrades

Implemented on `bug-fixes-v2` for the 0.4.0 release.

## Timeline / Time Travel

- Added `stackmap timeline --history <dir>` to merge dated StackMap JSON snapshots into one timeline IR.
- Added `--snapshot-dir <dir>` to `scan`, `scan-repo`, and `scan-aws` so scans can be written into a history directory as they run.
- Added `/api/timeline`:
  - `GET /api/timeline` returns snapshot metadata and precomputed diffs.
  - `GET /api/timeline?id=<snapshot-id>` returns the full graph for a specific snapshot.
- `stackmap serve --source <directory>` now detects a snapshot history directory and serves it as a timeline.
- The existing time-travel slider can now jump between saved snapshots.

## Security Findings

- Added `stackmap/findings/security.py` with detectors for:
  - public S3 ACLs and public bucket policies
  - internet-open sensitive security group ports
  - wildcard IAM policies with `Action: "*"` and `Resource: "*"`
  - unencrypted EBS volumes
  - CloudFront distributions missing access logging
- Security detectors are now included in the existing `/api/findings` analysis pass.
- Findings now paint affected graph nodes with severity halos.
- Finding filters now narrow the graph to affected resources.

## Multi-Account / Organization Surface

- Formalized top-level optional IR fields for `organization`, `timeline`, and `aggregates` while preserving the existing `metadata.organization` compatibility path.
- Existing organization scan/view behavior continues to work, with top-level organization data available to newer clients.
- Added `tests/fixtures/multi-account.json` with organization, OU, account, and cross-account edge coverage.

## Semantic Zoom

- Added frontend zoom tier state:
  - `overview` below 35%
  - `mid` below 80%
  - `detail` at 80% and above
- At overview zoom, architecture mode renders component aggregate nodes instead of every individual resource when component summaries are available.
- The minimap now renders a stable overview from component centroids even when the main canvas is in mid/detail zoom.
- Added a 500-node aggregate precompute performance guard for overview, mid, and detail tiers.
- The canvas updates zoom scale in the store on every zoom event.

## Cost Anomalies

- Added anomaly metadata support to cost reports.
- `/api/cost` accepts optional `actuals` in POST bodies and marks resources whose actual monthly cost is at least 30% above forecast.
- Cost overlay now shows an expandable Anomalies section with severity, ratio, and delta.

## Natural-Language Query

- Added `POST /api/nl-query`.
- Implemented a local deterministic query fallback for prompts like:
  - `show public resources`
  - `who depends on appdb`
  - `show databases`
  - `show lambda functions`
  - `show expensive resources`
- SearchBar now has a `text` / `query` toggle. In query mode, Enter applies the local server-returned transient graph filter.

## AWS Profile Switcher

- Added profile discovery from `~/.aws/config` and `~/.aws/credentials`.
- Added `/api/profiles` and `/api/profiles/activate`.
- Live AWS sessions are now held in a shared server state object, allowing profile activation without restarting the viewer.
- InsightsDock now exposes a profile picker when profiles are available.

## Packaged UI

- Rebuilt packaged static frontend assets under `stackmap/webapp/static` so installed builds receive the upgraded UI.

## Smart Grouping v2

- Expanded auto grouping beyond simple tag/network buckets:
  - environment, region, and account parent scopes
  - service/workload and team/owner tags
  - Terraform module paths
  - CloudFormation/SAM stack names
  - shared IAM roles for compute resources
  - naming prefix, VPC, subnet, and connectivity fallbacks
- Added group scoring helpers and metadata:
  - `confidence`
  - `reason`
  - `signals`
  - `dominant_categories`
  - hierarchy `parent` links
- Updated suggested grouping rules to emit env/team/module suggestions with confidence metadata.
- Component landing now treats smart groups as first-class components, with:
  - View All option
  - parent-scope filter chips
  - confidence pips
  - reason captions
  - parent sections
  - unlinked bucket only for resources no smart group claimed
- Detail panel now shows smart-group reasons and signal chips for selected resources.
- Added docs in `docs/smart-groups.md`.

## Step Functions Viewer

- Added `stackmap/parsers/asl.py` to parse Amazon States Language into a structured `asl_graph`.
- Terraform, CloudFormation/SAM, and live AWS parsing now persist `asl_graph` on state-machine nodes when definitions are available.
- Step Functions Task resources now emit kind-labeled edges such as `invokes`, `publishes`, `writes`, `queries`, `sends`, `emits`, and `starts`.
- Live AWS Step Functions scanning now uses ASL parsing instead of raw ARN regex extraction for Task edges.
- Added a dedicated main-canvas Step Functions workflow graph mode opened from **Open workflow graph** in the state-machine detail panel.
- Workflow graph mode now uses a lane-free flow layout, not the architecture layer system.
- Added Step Functions-specific icons for Pass, Choice, Task, Map, Parallel, Wait, Succeed, and Fail nodes.
- Workflow graph mode renders ASL states as normal StackMap graph nodes with labeled `next`, `choice`, `default`, `catch`, and retry/error paths.
- Warning overlays now appear directly on affected ASL states.
- Added **Show target resources** for mirrored Task targets, with click-through back to the real architecture resource.
- Added on-demand recent execution summaries from the workflow graph. No scan flag is needed; the viewer calls `states:ListExecutions` only when the user clicks **Load recent executions**.
- Added selected-execution debugging via `/api/sfn-execution-history`, calling `states:GetExecutionHistory` for one selected execution only and overlaying per-state status on the workflow graph.
- Added `stackmap aws-policy --addon stepfunctions` for optional `states:ListExecutions` and `states:GetExecutionHistory` permissions without expanding the default scan policy.
- Added typed frontend ASL contract and store getter for state-machine graphs.
- Added state-machine detail rendering:
- Removed the older stacked Step Functions card viewer in favor of the single graph-mode experience.
- Added docs in `docs/step-functions.md`.

## Validation

- Added backend coverage in `tests/test_roadmap_features.py` for:
  - timeline snapshot merging
  - security finding detectors
  - multi-account organization fixtures
  - semantic zoom aggregate performance
  - local NL query matching
  - AWS profile discovery
- Added smart-group v2 coverage for hierarchy, confidence/reason helpers, module paths, shared roles, and multi-region/multi-account parent roots.
- Added ASL parser coverage for Lambda Tasks, `.sync:2`, Choice, Parallel, classic and Distributed Map, Catch, unreachable states, and missing terminal states.
- Verification commands run:
  - `./.venv/bin/python -m pytest`
  - `npm --prefix frontend run build`
  - `./.venv/bin/python -m stackmap.webapp.build_assets --clean`

## Notes

- The NL query endpoint currently uses the safe local parser. Provider-backed work remains deferred to avoid adding local-tool cost or privacy risk.
- Semantic zoom uses existing component summaries for overview rendering, with backend aggregate precompute available for group-level summaries.
