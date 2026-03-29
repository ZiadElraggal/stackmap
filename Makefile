.PHONY: install test lint format frontend-build sync-webapp-assets package-build package build-package phase4-check

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
	python3 -m build

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
