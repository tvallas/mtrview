.PHONY: install test lint format build lock update-deps install-hooks check-commits verify

default: test

install:
	uv sync --group dev

install-hooks:
	git config core.hooksPath .githooks

check-commits:
	python3 scripts/check_conventional_commits.py --range "$$(git merge-base HEAD origin/master)..HEAD"

verify: check-commits lint test build

test:
	uv run pytest -v

lint:
	uv run ruff check .

format:
	uv run ruff format .

build:
	uv build

lock:
	uv lock

update-deps:
	uv lock --upgrade
	uv sync --group dev

