.PHONY: install test lint format frontend-build sync-webapp-assets package-build package build-package phase1-check phase2-check phase3-check phase4-check demo-check

install:
	pip install -e ".[dev]"

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

## Run a full check of the 4th phase of the stackmap development process, including frontend build, linting, type checking, testing, and scanning.
phase4-check:
	cd frontend && npm install
	cd frontend && rm -rf .nuxt .output && npm run generate
	python3 -m stackmap.webapp.build_assets --clean
	ruff check .
	mypy stackmap/
	pytest -q
	stackmap scan --source tests/fixtures/medium-step-functions.tfstate --format html --output /tmp/stackmap-phase4-check.html
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
