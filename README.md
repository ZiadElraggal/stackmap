# StackMap

Architecture diagrams that generate themselves from your infrastructure code and live AWS accounts.

StackMap is a CLI-first infrastructure visualization and architecture inference tool. It scans real infrastructure inputs, live AWS accounts, and repository sources, then produces interactive architecture maps with inferred relationships, smart grouping, cost forecasting, drift detection, live logs, billing-aware usage imports, and editable presentation workflows.

Instead of keeping diagrams up to date by hand, you point StackMap at what actually exists, inspect the evidence behind the generated graph, refine anything inference cannot know, and share the result as JSON, HTML, or the local interactive viewer.

## What StackMap Does

StackMap turns infrastructure into:

- interactive architecture diagrams
- grouped system/component views for larger graphs
- evidence-rich inferred service relationships
- editable architecture maps when inference is incomplete
- diffable snapshots of infrastructure over time
- live AWS operational context when explicitly enabled
- exportable HTML and JSON outputs

It is designed for platform engineers, DevOps teams, cloud architects, and anyone who needs fast, trustworthy architecture visibility from real infrastructure.

## Core Capabilities

### Infrastructure scanning and parsing

StackMap can work with:

- Terraform state
- CloudFormation templates / JSON
- AWS SAM-style inputs
- repository-wide infrastructure discovery
- live AWS account scans
- multi-account AWS scans

### Interactive architecture UI

The StackMap web UI supports:

- zooming and panning
- search
- category and relationship filtering
- component landing views for large graphs
- smart grouping overlays for large AWS graphs
- edge confidence and evidence inspection for inferred live AWS relationships
- low-confidence edge filtering
- dependency tracing from the detail panel
- findings and suspicious-pattern surfacing
- forecasted cost overlays with per-resource usage inputs
- optional AWS billing and CloudWatch usage import for current-vs-forecast cost comparisons
- optional CloudWatch log viewer for selected resources or all visible resources
- drift badges and summary bars when comparing IaC vs live state
- minimap navigation
- diff and timeline-oriented views
- presentation mode

### Edit and correction mode

StackMap is not only a viewer. It also supports correcting the generated architecture when inference is incomplete.

Current editor features include:

- hide noisy resources
- restore hidden resources
- add custom nodes
- add custom links
- recolor custom links
- move nodes between layers
- reorder nodes within the same layer
- create custom layers
- reorder layers
- delete empty custom layers
- undo / redo
- import / export local edit overlays

### Layered architecture model

StackMap organizes infrastructure into architecture lanes such as:

- frontend
- api
- serverless
- compute
- security/auth
- data

Users can also create custom layers for diagrams that need more structure than the default model.

### Multi-account AWS visibility

StackMap can scan across multiple AWS accounts and merge them into one graph. This is useful when systems are split across development, sandbox, shared services, and production accounts.

Supported multi-account patterns include:

- explicit account / role assumption input
- AWS named profile-based scanning
- cross-account edge visualization when relevant

### Live AWS relationship inference

Live AWS scans now run a post-scan inference pass after resources are collected. The goal is to turn a raw inventory into a useful architecture graph.

The inference engine can resolve relationships such as:

- API Gateway REST/v2 routes invoking Lambda functions from integration URIs
- API Gateway invoking Lambda functions from Lambda resource policies and execute-api `SourceArn`
- Lambda and ECS workloads accessing DynamoDB, S3, SQS, SNS, Secrets Manager, Step Functions, and related services from IAM role policies
- Lambda event source mappings from DynamoDB Streams, SQS, and Kinesis
- CloudFront origins pointing at S3, ALB, API Gateway, or custom origins when resolvable
- Route53 aliases and records pointing at CloudFront, ALB, API Gateway, and S3 endpoints when resolvable
- ALB/NLB listener and target group paths into ECS services, EC2 instances, IP targets, or Lambda targets where AWS exposes that data
- ECS services connected to task definitions, task roles, target groups, security groups, subnets, and downstream resources inferred from task role permissions

Each inferred edge can include metadata such as rule name, confidence, human-readable evidence, and the AWS API calls that supplied the evidence. High confidence means direct AWS configuration points to the target, medium confidence usually means IAM policy or SourceArn evidence implies the relationship, and low confidence is reserved for heuristics or network reachability context.

StackMap intentionally does not treat shared VPCs or shared security groups as application data flow by default. Network relationships are useful topology context, but functional data-flow edges require stronger evidence.

### Diff / timeline support

StackMap can compare infrastructure snapshots and visualize:

- added resources
- removed resources
- modified resources
- changed-only views

### AWS-aware visuals

The UI supports AWS-specific visual identity with official AWS icon assets where mapped, plus fallbacks for unmapped resource types.

## Installation

### Recommended: Homebrew on macOS

Stable install:

```bash
brew tap ziadelraggal/homebrew-stackmap
brew install ziadelraggal/homebrew-stackmap/stackmap
```

Verify install:

```bash
stackmap version
stackmap --help
```

Update:

```bash
brew upgrade stackmap
```

Uninstall:

```bash
brew uninstall stackmap
```

### Bleeding-edge Homebrew install from source

If you want the latest unreleased changes:

```bash
brew tap ziadelraggal/homebrew-stackmap
brew install --HEAD ziadelraggal/homebrew-stackmap/stackmap
```

### Install from source

Requirements:

- Python 3.10+
- Node.js and npm for frontend asset generation when packaging locally

Clone and install:

```bash
git clone https://github.com/ziadelraggal/stackmap.git
cd stackmap
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

Verify:

```bash
stackmap version
stackmap --help
```

### Windows: winget

Install via [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/):

```powershell
winget install ZiadElraggal.StackMap
```

Verify install:

```powershell
stackmap version
stackmap --help
```

Update:

```powershell
winget upgrade ZiadElraggal.StackMap
```

Uninstall:

```powershell
winget uninstall ZiadElraggal.StackMap
```

New releases are automatically submitted to the winget package repository when a GitHub Release is published, just like Homebrew.

## Quick Start

### 1. Scan a Terraform state file

```bash
stackmap scan --source terraform.tfstate --format json --output stackmap-output.json
```

Or generate an interactive HTML output:

```bash
stackmap scan --source terraform.tfstate --format html --output stackmap-output.html
```

### 2. Serve the interactive UI locally

```bash
stackmap serve --source terraform.tfstate
```

Serve with drift detection against a second source:

```bash
stackmap serve --source terraform.tfstate --drift-against aws-live.json
```

If `stackmap-output.json` already exists, you can also serve that:

```bash
stackmap serve --source stackmap-output.json
```

### 3. Scan an entire repository

```bash
stackmap scan-repo . --output stackmap-repo-output.json
```

### 4. Scan live AWS infrastructure

Single account / profile:

```bash
stackmap scan-aws --profile dev --output aws-output.json --serve
```

Enable live CloudWatch logs in the viewer for that profile:

```bash
stackmap scan-aws --profile dev --output aws-output.json --serve --live-logs
```

Enable AWS billing and usage metric imports in the viewer:

```bash
stackmap scan-aws --profile dev --output aws-output.json --serve --live-billing
```

Multi-account via named profiles:

```bash
stackmap scan-aws --account-profiles dev,sandbox --output multi.json --serve
```

Multi-account via explicit role assumption:

```bash
stackmap scan-aws \
  --accounts 'dev:arn:aws:iam::111122223333:role/StackMapReadOnly,sandbox:arn:aws:iam::444455556666:role/StackMapReadOnly' \
  --output multi.json \
  --serve
```

### 5. Compare two infrastructure snapshots

```bash
stackmap diff before.json after.json --output stackmap-diff.json
```

## Main CLI Commands

### `stackmap scan`

Parses a single infrastructure source and produces JSON or HTML output.

Use this for:

- Terraform state files
- CloudFormation JSON
- other directly supported source files

### `stackmap scan-repo`

Discovers infrastructure sources across a repository, merges them, and produces a unified graph.

Use this when:

- infrastructure is spread across multiple directories
- you want repo-level architecture visibility
- you want Terraform, CloudFormation, and SAM discovered together

### `stackmap scan-aws`

Scans live AWS infrastructure through read-only APIs.

Use this for:

- current-state architecture maps
- multi-account visibility
- environments that are not fully represented in code snippets alone
- relationship inference from live AWS configuration
- optional live logs and billing-aware usage imports when explicitly enabled

### `stackmap serve`

Launches the interactive local web UI for exploring a graph.

Use this when:

- you want the full StackMap experience
- you want editing, filtering, or presentation workflows
- you want to inspect large graphs interactively

Useful options:

- `--drift-against <file>` compares the served graph against another snapshot and enables drift badges in the UI
- `--auto-group/--no-auto-group` controls smart grouping during serve
- `--aws-profile <profile> --live-logs` enables the CloudWatch log viewer for locally served graphs when the profile has the separate logs policy
- `--aws-profile <profile> --live-billing` enables AWS billing and CloudWatch usage metric imports when the profile has the separate billing policy

### `stackmap diff`

Computes a diff between two infrastructure snapshots and outputs a graph with change metadata.

### `stackmap org-import`

Imports / overlays organization data for AWS organization-aware views.

### `stackmap aws-policy`

Builds AWS IAM policy documents for StackMap.

By default it prints the base read-only scan policy:

```bash
stackmap aws-policy
```

Optional live features are separate add-on policies, not part of the default scan policy:

```bash
stackmap aws-policy --addon logs
stackmap aws-policy --addon billing
```

### `stackmap setup-org-role`

Helps set up an AWS Organizations-compatible read-only role flow for scanning.

### `stackmap version`

Prints the installed StackMap version.

## Interactive UI Features

When you open the StackMap UI, you get:

- architecture graph rendering
- service-specific nodes and AWS-aware icons
- relationship lines and animated flows
- graph grouping
- search
- filter sidebar
- detail panel
- keyboard shortcuts
- timeline / diff controls
- edit mode

### Advanced insight panels

#### Smart grouping

Smart grouping is currently applied automatically during `stackmap serve` unless you disable it with `--no-auto-group`.

For live AWS scans, StackMap also applies a live-account grouping pass during scan assembly. That pass uses tags and inferred service relationships before falling back to network-level context.

The grouping engine prioritizes:

1. CloudFormation or SAM stack membership from tags such as `aws:cloudformation:stack-name`
2. business tags such as `service`, `app`, `application`, `project`, `component`, and environment labels
3. connected components formed by high/medium-confidence functional edges
4. API entrypoint expansion from API Gateway, CloudFront, or ALB into downstream Lambda, ECS, and data stores
5. naming-family fallback with normalized resource-name tokenization
6. VPC or subnet grouping only as a fallback

Earlier strategies win, so a CloudFormation/SAM or business-tagged application cluster is preferred over a lower-signal VPC bucket. This keeps the UI focused on business components first and infrastructure topology second.

Auto-generated groups can include metadata such as grouping strategy, confidence, evidence, entrypoints, account IDs, regions, and resource counts by type. The detail panel shows a smart group reason when that metadata is available.

#### Relationship evidence and architecture inference

Live AWS scans attach evidence metadata to inferred relationships whenever possible.

Example edge metadata:

```json
{
  "source": "aws_live_inference",
  "inference_rule": "apigateway_lambda_integration_uri",
  "confidence": "high",
  "evidence": "API Gateway integration URI references arn:aws:lambda:us-east-1:123456789012:function:orders-handler",
  "api_calls": ["apigateway:get_integration"]
}
```

The UI surfaces this in the edge detail panel so users can see why an edge exists instead of treating generated architecture as a black box.

Default architecture views prioritize functional relationships such as `triggers`, `routes_to`, `reads_from`, `writes_to`, and `cross_account_reference`. Lower-signal relationship types such as generic references, IAM/auth edges, and network reachability context remain available for inspection and filtering without overwhelming the main architecture view.

#### Cost forecasting

The cost panel in the UI is a forecast overlay by default. It becomes billing-aware only when live billing is explicitly enabled.

Current behavior:

- StackMap computes a baseline monthly estimate from resource metadata and bundled pricing heuristics
- the top-right cost panel shows total forecast plus top components and category totals
- the detail panel lets you add resource-level usage inputs such as Lambda memory, invocations, duration, storage GB, and transfer GB
- when you add inputs, StackMap recomputes the estimate and shows the delta from the baseline forecast

Optional live usage import:

- With `--live-billing`, StackMap can pull AWS Cost Explorer totals and CloudWatch usage metrics for supported services, then recalculate the forecast from those usage inputs.
- Without `--live-billing`, the UI stays on local heuristic forecasting and never calls AWS billing or CloudWatch metrics APIs.
- Supported usage imports include Lambda invocations/duration, S3 storage and transfer-related metrics where available, DynamoDB/SQS-style service metrics where mapped, and CloudFront `BytesDownloaded` for replacing the default 100 GB transfer assumption.

#### Live CloudWatch logs

Live logs are optional and only run when you explicitly enable them:

```bash
stackmap scan-aws --profile dev --serve --live-logs
```

This keeps the default AWS scan on the minimal read-only policy. If your AWS profile also has the separate live logs policy attached, the UI shows a `Live logs` toggle in the Insights panel and a `View CloudWatch logs` button for supported resources in the detail panel.

The log panel can fetch the last hour, 6 hours, 24 hours, or 7 days, and can aggregate logs from all currently visible resources in the graph.

The live logs policy is separate from the normal scan policy so teams can review and attach it only when they want CloudWatch log access:

```bash
stackmap aws-policy --addon logs
```

The packaged policy file is also available for review at `stackmap/cli/aws_policy_live_logs.json`.

#### AWS billing and usage imports

AWS billing is also optional and separate from the default scan policy:

```bash
stackmap scan-aws --profile dev --serve --live-billing
```

When enabled, the Cost & Usage panel can fetch AWS usage metrics for all supported resources and recalculate the forecast. Individual resources can also fetch their own usage from the detail panel. CloudFront distributions use the CloudWatch `BytesDownloaded` metric to replace the default transfer estimate when available.

The billing policy is separate from the normal scan policy:

```bash
stackmap aws-policy --addon billing
```

#### Drift detection

Drift detection is enabled by serving one graph against another:

```bash
stackmap serve --source desired.json --drift-against live.json
```

Current behavior:

1. StackMap normalizes both graphs into a shared comparison model
2. it matches resources across the two graphs
3. it compares a curated set of important properties for known resource types
4. it compares relationships to detect missing or extra connections
5. it annotates the served IR so the UI can show resource badges and summary counts

Unknown resource types fall back to a broader property comparison with unstable keys such as IDs, ARNs, and timestamps ignored.

### Edit mode details

Edit mode is intended as a correction layer over real infrastructure, not a fully manual diagram editor.

Current edit capabilities:

- Inspect mode for safe browsing
- Structure mode for layer moves, hide/show, and architecture cleanup
- Connect mode for manual relationships
- custom nodes and custom links
- layer management
- node reordering within a lane
- presentation cleanup workflows

Edits are currently persisted locally in the browser and can also be exported/imported as edit overlay JSON.

## Typical Workflows

### Generate from Terraform and present it

```bash
stackmap scan --source terraform.tfstate --format json --output stackmap-output.json
stackmap serve --source stackmap-output.json
```

Then in the UI:

- hide noisy resources
- add any missing links
- tidy the architecture layout
- switch to presentation mode

### Understand a large repository

```bash
stackmap scan-repo . --output stackmap-repo-output.json
stackmap serve --source stackmap-repo-output.json
```

Then:

- use component landing view
- isolate components / layers
- filter relationships
- navigate the architecture incrementally

### Map multiple AWS accounts

```bash
stackmap scan-aws --account-profiles dev,sandbox,shared --output org.json --serve
```

Then:

- inspect account groupings
- look for cross-account links
- focus only the portion of the system you want to present

## Output Formats

### JSON

Useful for:

- automation
- testing
- feeding the interactive viewer
- product demos / scripted website demos

### HTML

Useful for:

- sharing architecture snapshots
- lightweight presentation artifacts
- generated outputs without running the local dev UI

## Development

### Contributor setup

```bash
make install-dev
```

### Helpful commands

Build frontend static assets:

```bash
make frontend-build
```

Sync generated frontend assets into the packaged Python web bundle:

```bash
make sync-webapp-assets
```

Build the Python package:

```bash
make package-build
```

Run tests:

```bash
make test
```

Lint:

```bash
make lint
```

Format:

```bash
make format
```

## Packaging and Release Flow

### Homebrew release automation

On GitHub Release publish (`vX.Y.Z`), the `Homebrew Release` workflow:

1. Builds the frontend static app from the tagged source.
2. Syncs generated assets into the Python package bundle.
3. Creates a release source archive and uploads it to the GitHub Release.
4. Computes the archive SHA256 and renders a stable `stackmap.rb` formula.
5. Uploads the formula as a workflow artifact.
6. Pushes the formula update to the Homebrew tap if configured.

### Windows / winget release automation

On GitHub Release publish (`vX.Y.Z`), the `Windows Release` workflow:

1. Builds the frontend static app from the tagged source.
2. Syncs generated assets into the Python package bundle.
3. Installs StackMap plus PyInstaller on `windows-latest`.
4. Builds a standalone `stackmap.exe` and uploads it to the GitHub Release.
5. Uses `wingetcreate` to automatically submit an updated manifest PR to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs).

You can also run the workflow manually from Actions to generate a Windows artifact before cutting a public release.

### Required GitHub configuration for automatic releases

- repository variable: `HOMEBREW_TAP_REPO`
  - example: `ziadelraggal/homebrew-stackmap`
- repository secret: `HOMEBREW_TAP_TOKEN`
  - token with push access to that tap repo
- repository secret: `WINGET_PAT`
  - a GitHub PAT with `public_repo` scope, used by `wingetcreate` to fork `microsoft/winget-pkgs` and open manifest update PRs

### Release flow

1. Bump version in [pyproject.toml](/Users/ziadelraggal/Documents/GitHub/stackmap/pyproject.toml).
2. Merge to `main`.
3. Create and publish a GitHub Release tag in `vX.Y.Z` format.
4. Wait for workflows `Homebrew Release` and `Windows Release` to complete.
5. macOS users can then run:

```bash
brew upgrade stackmap
```

6. Windows users can then run:

```powershell
winget upgrade ZiadElraggal.StackMap
```

## Project Direction

StackMap is evolving into a hybrid of:

- infrastructure scanner
- architecture inference engine
- multi-account mapper
- interactive explorer
- architecture correction and presentation tool

The product direction is intentionally:

- generated-first
- reality-based
- CLI-first
- presentation-friendly

## Troubleshooting

### `stackmap` command not found after install

Run:

```bash
brew doctor
brew --prefix
stackmap version
```

If installed from source, make sure your virtual environment is active or the install location is on your `PATH`.

### Homebrew release does not show latest UI changes

Recent releases now build the packaged frontend in CI before publishing the release artifact used by Homebrew. If a just-published release is not yet available, wait for the `Homebrew Release` workflow to finish and then try:

```bash
brew upgrade stackmap
```

### AWS scan permissions

If a live AWS scan fails due to missing permissions, use:

```bash
stackmap aws-policy
```

to generate a read-only policy template for scanning.

Optional live UI features use separate policies that can be reviewed and attached independently:

```bash
stackmap aws-policy --addon logs
stackmap aws-policy --addon billing
```

The same reviewable JSON files are included in the package:

- `stackmap/cli/aws_policy.json`
- `stackmap/cli/aws_policy_live_logs.json`
- `stackmap/cli/aws_policy_billing.json`

## License

MIT
