.PHONY: install run test lint format check

install:
	uv sync --all-extras

run:
	uv run uvicorn ai_cicd_demo.main:app --reload

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run mypy src

format:
	uv run ruff format .
	uv run ruff check --fix .

check: lint test
