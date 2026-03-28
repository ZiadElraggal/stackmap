.PHONY: install test lint format

install:
	pip install -e ".[dev]"

test:
	pytest || test $$? -eq 5

lint:
	ruff check . && mypy stackmap/

format:
	ruff format .
