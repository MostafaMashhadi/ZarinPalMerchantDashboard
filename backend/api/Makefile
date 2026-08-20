.PHONY: format lint test check

format:
	ruff format .

lint:
	ruff check .

test:
	pytest

# CI-equivalent local gate: run before every push / PR.
check: lint test
