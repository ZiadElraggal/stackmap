.PHONY: install-dev brew-install brew-upgrade brew-uninstall test lint format frontend-build sync-webapp-assets package-build package build-package release-check phase1-check phase2-check phase3-check phase4-check demo-check

install-dev:
	pip install -e ".[dev]"

brew-install:
	brew tap ziadelraggal/homebrew-stackmap
	brew install ziadelraggal/homebrew-stackmap/stackmap

brew-upgrade:
	brew upgrade stackmap

brew-uninstall:
	brew uninstall stackmap || true

test:
	pytest || test $$? -eq 5

lint:
	ruff check . && mypy stackmap/

format:
	ruff format .

frontend-build:
	cd frontend && npm install
	cd frontend && rm -rf .nuxt .output && npm run generate

sync-webapp-assets:
	python3 -m stackmap.webapp.build_assets --clean

package-build: frontend-build sync-webapp-assets
	python3 -m pip install --upgrade build setuptools wheel
	python3 -m build --no-isolation

# Convenience aliases for packaging
package: package-build

build-package: package-build

release-check: package-build
	./.venv/bin/stackmap scan --source tests/fixtures/sam-simple.json --format json --output /tmp/stackmap-release-check.json
	./.venv/bin/stackmap serve --source tests/fixtures/sam-simple.json --host 127.0.0.1 --port 3011 --no-open >/tmp/stackmap-release-check.log 2>&1 & pid=$$!; \
	sleep 2; \
	curl -sf http://127.0.0.1:3011/api/health; \
	curl -sf http://127.0.0.1:3011/api/graph > /tmp/stackmap-release-graph.json; \
	curl -sf http://127.0.0.1:3011/ > /tmp/stackmap-release-index.html; \
	! grep -q '@vite/client' /tmp/stackmap-release-index.html; \
	! grep -q 'node_modules/nuxt/dist/app/entry.js' /tmp/stackmap-release-index.html; \
	kill $$pid; wait $$pid 2>/dev/null || true
	@echo "Release check passed."

## Run a full check of the 4th phase: frontend build, phase gates, and Terraform/CFN scans.
phase4-check:
	cd frontend && npm install
	cd frontend && rm -rf .nuxt .output && npm run generate
	python3 -m stackmap.webapp.build_assets --clean
	pytest -q tests/parsers/test_phase1_terraform_accuracy.py tests/parsers/test_phase2_relationship_expansion.py tests/parsers/test_phase3_architecture_clarity.py tests/parsers/test_phase4_cloudformation.py tests/parsers/test_demo_readiness.py tests/parsers/test_additional_fixtures_smoke.py tests/cli/test_main.py
	stackmap scan --source tests/fixtures/medium-step-functions.tfstate --format html --output /tmp/stackmap-phase4-check.html
	stackmap scan --source tests/fixtures/cloudformation-simple.json --format json --output /tmp/stackmap-phase4-cfn.json
	stackmap serve --help > /dev/null
	@echo "Phase 4 check passed."

## Customer demo readiness: parser relationship quality + architecture clarity smoke.
demo-check:
	pytest -q tests/parsers/test_demo_readiness.py tests/parsers/test_additional_fixtures_smoke.py

## Phase 1 gate: Terraform parsing accuracy baseline + demo readiness.
phase1-check:
	pytest -q tests/parsers/test_phase1_terraform_accuracy.py tests/parsers/test_demo_readiness.py tests/parsers/test_additional_fixtures_smoke.py

## Phase 2 gate: expanded Terraform relationship extraction.
phase2-check:
	pytest -q tests/parsers/test_phase1_terraform_accuracy.py tests/parsers/test_phase2_relationship_expansion.py tests/parsers/test_demo_readiness.py tests/parsers/test_additional_fixtures_smoke.py

## Phase 3 gate: architecture projection clarity + frontend compile sanity.
phase3-check:
	pytest -q tests/parsers/test_phase1_terraform_accuracy.py tests/parsers/test_phase2_relationship_expansion.py tests/parsers/test_phase3_architecture_clarity.py tests/parsers/test_demo_readiness.py tests/parsers/test_additional_fixtures_smoke.py
	cd frontend && npm run generate
