.PHONY: install run test lint format check coverage

install:
	uv sync --all-extras

run:
	uv run uvicorn ai_cicd_demo.main:app --reload

test:
	uv run pytest -v

coverage:
	uv run pytest --cov=src --cov-report=term-missing --cov-report=xml --cov-report=html

lint:
	uv run ruff check .
	uv run mypy src

format:
	uv run ruff format .
	uv run ruff check --fix .

check: lint test
