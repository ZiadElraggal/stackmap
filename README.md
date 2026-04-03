# StackMap

Architecture diagrams that generate themselves from your infrastructure code.

## Install (Homebrew)

StackMap is distributed as a CLI-first tool via Homebrew.

### Stable install (recommended)

```bash
brew tap ziadelraggal/homebrew-stackmap
brew install ziadelraggal/homebrew-stackmap/stackmap
```

### Update

```bash
brew upgrade stackmap
```

### Uninstall

```bash
brew uninstall stackmap
```

### Install bleeding-edge from source (optional)

```bash
brew tap ziadelraggal/homebrew-stackmap
brew install --HEAD ziadelraggal/homebrew-stackmap/stackmap
```

## Release automation for Homebrew tap

On GitHub Release publish (`vX.Y.Z`), the `Homebrew Release` workflow:

1. Builds the frontend static app from the tagged source.
2. Syncs generated assets into the Python package bundle.
3. Creates a release source archive and uploads it to the GitHub Release.
4. Computes the archive SHA256 and renders a stable `stackmap.rb` formula.
5. Uploads the formula as a workflow artifact.
6. Pushes the formula update to your tap repo (`homebrew-stackmap`) if configured.

### Required configuration for automatic tap updates

- GitHub repository variable: `HOMEBREW_TAP_REPO`
  - Example: `ziadelraggal/homebrew-stackmap`
- GitHub repository secret: `HOMEBREW_TAP_TOKEN`
  - Token with push access to that tap repo.

## Publish flow (what you do each release)

1. Bump version in `pyproject.toml`.
2. Merge to `main`.
3. Create and publish a GitHub Release tag in `vX.Y.Z` format.
4. Wait for workflow `Homebrew Release` to complete. It will build the packaged release archive and update the Homebrew tap.
5. Users can run `brew upgrade stackmap` and get the new version.

## Development setup (contributors)

For local development/testing only:

```bash
make install-dev
```
