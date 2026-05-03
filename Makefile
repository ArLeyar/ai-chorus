# ai-chorus — local dev workflow.
# Mirrors the CI gates (.github/workflows/ci.yml) so you can verify before push.
#
# Quick start:
#   make install    # one-time: uv sync (runtime + dev)
#   make hooks      # one-time: install pre-commit hook
#   make check      # run all CI checks locally before push

.PHONY: help install hooks fmt fmt-check lint lint-fix type test test-fast review review-dry-run check clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## uv sync — install runtime + dev deps
	uv sync

hooks:  ## Install pre-commit git hook (one-time)
	uv run pre-commit install

fmt:  ## Apply ruff formatting
	uv run ruff format src tests

fmt-check:  ## Check ruff formatting (no changes)
	uv run ruff format --check src tests

lint:  ## Run ruff lint
	uv run ruff check src tests

lint-fix:  ## Run ruff lint with auto-fix
	uv run ruff check --fix src tests

type:  ## Run mypy --strict
	uv run mypy src

test:  ## Run pytest with coverage report
	uv run pytest --cov --cov-report=term-missing

test-fast:  ## Run pytest without coverage (faster)
	uv run pytest -q

review:  ## Post the multi-model review for HEAD~1..HEAD (requires API keys + PR_NUMBER)
	uv run python -m chorus.review

review-dry-run:  ## Print review markdown to stdout instead of posting
	uv run python -m chorus.review --dry-run

check: fmt-check lint type test  ## Run all CI gates (lint, format, type, test)

clean:  ## Remove build/cache artifacts
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache htmlcov
	rm -f .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
