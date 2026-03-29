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

1. Computes the release archive SHA256.
2. Renders a stable `stackmap.rb` formula.
3. Uploads formula as a workflow artifact.
4. Pushes formula update to your tap repo (`homebrew-stackmap`) if configured.

### Required configuration for automatic tap updates

- GitHub repository variable: `HOMEBREW_TAP_REPO`
  - Example: `ziadelraggal/homebrew-stackmap`
- GitHub repository secret: `HOMEBREW_TAP_TOKEN`
  - Token with push access to that tap repo.

## Publish flow (what you do each release)

1. Bump version in `pyproject.toml`.
2. Merge to `main`.
3. Create and publish a GitHub Release tag in `vX.Y.Z` format.
4. Wait for workflow `Homebrew Release` to complete.
5. Users can run `brew upgrade stackmap` and get the new version.

## Development setup (contributors)

For local development/testing only:

```bash
make install-dev
```
