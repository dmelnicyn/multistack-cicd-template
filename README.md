# AI CI/CD Demo

A minimal FastAPI learning template for CI/CD with Python.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

Install uv if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setup

Clone the repository and install dependencies:

```bash
git clone <repo-url>
cd ai-cicd-demo
make install
```

Or without make:

```bash
uv sync --all-extras
```

## Commands

| Task | Make Command | Direct Command |
|------|--------------|----------------|
| Install deps | `make install` | `uv sync --all-extras` |
| Run server | `make run` | `uv run uvicorn ai_cicd_demo.main:app --reload` |
| Run tests | `make test` | `uv run pytest -v` |
| Lint code | `make lint` | `uv run ruff check . && uv run mypy src` |
| Format code | `make format` | `uv run ruff format . && uv run ruff check --fix .` |
| All checks | `make check` | Runs lint + test |

## Project Structure

```
ai-cicd-demo/
├── pyproject.toml          # Project config, dependencies, tool settings
├── uv.lock                  # Locked dependencies
├── Makefile                 # Developer commands
├── README.md                # This file
├── src/
│   └── ai_cicd_demo/
│       ├── __init__.py      # Package init
│       ├── main.py          # FastAPI app and endpoints
│       └── models.py        # Pydantic models
└── tests/
    ├── __init__.py
    └── test_main.py         # API tests using TestClient
```

## API Endpoints

- `GET /health` - Health check, returns `{"status": "ok"}`
- `GET /items/{item_id}` - Get item by ID (mock data)
- `GET /docs` - Swagger UI documentation (when server is running)

## Tooling

- **Dependency management**: [uv](https://docs.astral.sh/uv/)
- **Linting & formatting**: [ruff](https://docs.astral.sh/ruff/)
- **Type checking**: [mypy](https://mypy-lang.org/)
- **Testing**: [pytest](https://pytest.org/) with FastAPI TestClient

## CI

GitHub Actions runs on push to `main` and on pull requests:
- `make lint` — ruff + mypy
- `make test` — pytest

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## AI PR Summary

Automatically posts an AI-generated summary comment on pull requests, including:

- **Summary** — bullet points of key changes
- **Risk assessment** — Low/Medium/High with reasons
- **Suggested checks** — tests or manual verification based on changes
- **Grouped file list** — files organized by area (API, tests, config, etc.)

**Required Secret:** Add `OPENAI_API_KEY` to your repository secrets (Settings → Secrets → Actions).

If the secret is not configured, the workflow skips gracefully with a notice.

Security features:
- Potential secrets are redacted before sending to OpenAI
- Large diffs are truncated to prevent excessive API costs
- Minimal permissions (contents read, pull-requests write)

See [`.github/workflows/ai_pr_summary.yml`](.github/workflows/ai_pr_summary.yml).

## PR Title Convention

This repository enforces [Conventional Commits](https://www.conventionalcommits.org/) for PR titles.

**Format:** `type(scope)?: description`

**Allowed types:**
- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation
- `chore` — maintenance
- `refactor` — code refactoring
- `test` — tests
- `perf` — performance
- `ci` — CI/CD changes
- `build` — build system

**Examples:**
- `feat: add user profile endpoint`
- `fix(auth): handle missing token`
- `docs: update README`
