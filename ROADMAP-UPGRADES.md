# StackMap Roadmap Upgrades

Implemented on `bug-fixes-v2` after the 0.3.1 foundation work.

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

## Semantic Zoom

- Added frontend zoom tier state:
  - `overview` below 35%
  - `mid` below 80%
  - `detail` at 80% and above
- At overview zoom, architecture mode renders component aggregate nodes instead of every individual resource when component summaries are available.
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
- SearchBar now has a `text` / `ai` toggle. In `ai` mode, Enter applies the server-returned transient graph filter.

## AWS Profile Switcher

- Added profile discovery from `~/.aws/config` and `~/.aws/credentials`.
- Added `/api/profiles` and `/api/profiles/activate`.
- Live AWS sessions are now held in a shared server state object, allowing profile activation without restarting the viewer.
- InsightsDock now exposes a profile picker when profiles are available.

## Packaged UI

- Rebuilt packaged static frontend assets under `stackmap/webapp/static` so installed builds receive the upgraded UI.

## Validation

- Added backend coverage in `tests/test_roadmap_features.py` for:
  - timeline snapshot merging
  - security finding detectors
  - local NL query matching
  - AWS profile discovery
- Verification commands run:
  - `./.venv/bin/python -m pytest`
  - `npm --prefix frontend run build`
  - `./.venv/bin/python -m stackmap.webapp.build_assets --clean`

## Notes

- The NL query endpoint currently uses the safe local parser. It is ready for a provider-backed implementation later without changing the frontend contract.
- Semantic zoom uses existing component summaries for overview aggregation. A future backend aggregate precompute can populate the optional `aggregates` field for richer group-level edge rendering.
