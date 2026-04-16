# Manual Test Checklist: Roadmap Features

Use this when you want to visually verify the 0.3.1 roadmap work in the local browser UI.

Assume commands run from the repo root:

```bash
cd /Users/ziadelraggal/Documents/GitHub/stackmap
```

If port `3000` is busy, change `--port` to another value and open that URL.

## 1. Smoke Check The App

Start with a normal fixture:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source tests/fixtures/sam-simple.json \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

Open:

```text
http://127.0.0.1:3000
```

Check:

- The graph loads.
- Search bar appears.
- Insights/findings/cost UI opens without errors.
- Browser dev console has no obvious runtime errors.

Stop the server with `Ctrl-C` before starting the next scenario.

## 2. Timeline / Time Travel

Create a temporary timeline history:

```bash
mkdir -p /tmp/stackmap-timeline-manual
./.venv/bin/python -m stackmap.cli.main scan \
  --source tests/fixtures/timeline-before.json \
  --snapshot-dir /tmp/stackmap-timeline-manual \
  --output /tmp/stackmap-before.json
./.venv/bin/python -m stackmap.cli.main scan \
  --source tests/fixtures/timeline-after.json \
  --snapshot-dir /tmp/stackmap-timeline-manual \
  --output /tmp/stackmap-after.json
./.venv/bin/python -m stackmap.cli.main timeline \
  --history /tmp/stackmap-timeline-manual \
  --output /tmp/stackmap-timeline.json
```

Serve the timeline:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source /tmp/stackmap-timeline.json \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

Check:

- Time slider appears.
- Switching snapshots updates the graph.
- Diff legend appears.
- Added/removed/changed styling appears where applicable.
- Command palette has a jump-to-change action.

Optional API check:

```bash
curl -s http://127.0.0.1:3000/api/timeline
```

## 3. Security Findings

Serve the public S3 fixture:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source tests/fixtures/public-s3.tfstate \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

Check:

- Findings panel shows a public S3 finding.
- Affected node has severity styling/halo.
- Finding row shows severity and remediation.
- Clicking the finding filters/highlights the affected node.
- Selecting the affected node shows findings in the detail panel.

Stop and test open security group:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source tests/fixtures/open-sg.tfstate \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

Check:

- Findings panel shows an open sensitive port finding.
- Remediation accordion/details are visible.

Flag check:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source tests/fixtures/open-sg.tfstate \
  --no-security-findings \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

Check:

- Security-specific finding disappears.

## 4. Organization / Multi-Account View

Serve the multi-account fixture:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source tests/fixtures/multi-account.json \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

Check:

- App enters organization view or offers organization mode.
- Organization/root, OU, and account cards/groups are visible.
- Per-account filters work.
- Cross-account edges are visible when enabled.
- Toggling cross-account edges hides/shows those relationships.
- Breadcrumb/account scope updates when drilling into an account or OU.

Optional API check:

```bash
curl -s http://127.0.0.1:3000/api/graph | rg '"organization"|"cross_account_reference"'
```

## 5. Semantic Zoom And Minimap Overview

Use a larger fixture:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source tests/fixtures/complex-multi-vpc.tfstate \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

Check:

- Zoom out below roughly 35%.
- Graph switches to overview/component aggregate nodes.
- Zoom between roughly 35% and 80%.
- Graph switches to mid tier.
- Zoom in above roughly 80%.
- Detail nodes render again.
- Minimap stays stable and overview-like while the main graph changes tier.
- Command palette can lock zoom tier to overview/mid/detail.

## 6. Cost Anomalies

Serve a cost-capable fixture:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source tests/fixtures/sam-simple.json \
  --anomaly-thresholds 1.2,1.5,2.0 \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

In another terminal, inspect cost IDs:

```bash
curl -s http://127.0.0.1:3000/api/cost
```

Pick a `by_node` key from the response, then POST actuals that are above forecast:

```bash
curl -s -X POST http://127.0.0.1:3000/api/cost \
  -H "Content-Type: application/json" \
  -d '{"actuals":{"PASTE_NODE_ID_HERE":999}}'
```

Check:

- Cost overlay shows an Anomalies section.
- The anomalous node shows the anomaly sigil.
- Medium/high anomaly appears in the findings flow.
- Changing `--anomaly-thresholds` changes which ratios become low/medium/high.

## 7. Local Query Bar

Serve any fixture with mixed resources:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source tests/fixtures/timeline-after.json \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

In the search bar:

- Switch from `text` to `query`.
- Try `show public resources`.
- Try `show databases`.
- Try `show lambda functions`.
- Try `who depends on orders-table`.
- Try `show expensive resources` after loading cost data.

Check:

- The UI says why it matched.
- Matching nodes are filtered/highlighted.
- No external API key is required.
- The UI says `query`, not `AI`.

Optional API check:

```bash
curl -s -X POST http://127.0.0.1:3000/api/nl-query \
  -H "Content-Type: application/json" \
  -d '{"query":"show databases"}'
```

## 8. AWS Profile Switcher

This requires local AWS profile files. You do not need to hit AWS just to confirm profile discovery.

Start with a profile-aware server:

```bash
./.venv/bin/python -m stackmap.cli.main serve \
  --source tests/fixtures/sam-simple.json \
  --aws-profile default \
  --host 127.0.0.1 \
  --port 3000 \
  --no-open
```

Check:

- Profile switcher appears in the insights/profile area if profiles exist.
- Available profiles match `~/.aws/config` and `~/.aws/credentials`.
- Activating a profile updates the active profile label.
- If logs/cost/profile work is already in flight, switching is guarded/disabled.
- Errors use the same styling as other AWS/boto3 surfaces.

Optional API checks:

```bash
curl -s http://127.0.0.1:3000/api/profiles
curl -s -X POST http://127.0.0.1:3000/api/profiles/activate \
  -H "Content-Type: application/json" \
  -d '{"profile":"default"}'
```

## 9. Regression Checks

Run after manual testing:

```bash
./.venv/bin/python -m pytest
npm --prefix frontend run build
./.venv/bin/python -m stackmap.webapp.build_assets --clean
```

Expected:

- Pytest passes.
- Frontend build passes.
- Build may still warn about a large chunk; that warning is known.

## Intentional Skip

Do not test external/provider-backed natural-language parsing yet. That work is intentionally deferred.
