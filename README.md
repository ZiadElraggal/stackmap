# StackMap

Architecture diagrams that generate themselves from your infrastructure code.

StackMap is a CLI-first infrastructure visualization tool that scans real infrastructure inputs and produces interactive architecture maps. Instead of keeping diagrams up to date by hand, you point StackMap at what actually exists, then explore, refine, and present the result.

## What StackMap Does

StackMap turns infrastructure into:

- interactive architecture diagrams
- grouped system/component views for larger graphs
- editable architecture maps when inference is incomplete
- diffable snapshots of infrastructure over time
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

### `stackmap serve`

Launches the interactive local web UI for exploring a graph.

Use this when:

- you want the full StackMap experience
- you want editing, filtering, or presentation workflows
- you want to inspect large graphs interactively

### `stackmap diff`

Computes a diff between two infrastructure snapshots and outputs a graph with change metadata.

### `stackmap org-import`

Imports / overlays organization data for AWS organization-aware views.

### `stackmap aws-policy`

Builds a read-only AWS policy document suitable for StackMap scanning.

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

### Required GitHub configuration for automatic tap updates

- repository variable: `HOMEBREW_TAP_REPO`
  - example: `ziadelraggal/homebrew-stackmap`
- repository secret: `HOMEBREW_TAP_TOKEN`
  - token with push access to that tap repo

### Release flow

1. Bump version in [pyproject.toml](/Users/ziadelraggal/Documents/GitHub/stackmap/pyproject.toml).
2. Merge to `main`.
3. Create and publish a GitHub Release tag in `vX.Y.Z` format.
4. Wait for workflow `Homebrew Release` to complete.
5. Users can then run:

```bash
brew upgrade stackmap
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

## License

MIT
