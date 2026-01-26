# AI Usage Policy

This document describes how AI features in this repository handle data and what security controls are in place.

## What Data is Sent to OpenAI

### PR Summary / Test Draft Workflows

When a pull request is opened or updated, the following data may be sent to OpenAI:

- PR title and description
- File paths of changed files
- Diff patches (code changes, not full file contents)
- Commit messages associated with the PR

### Release Notes Workflow

When a version tag is pushed, the following data may be sent to OpenAI:

- Commit messages between the previous and current tag
- PR titles associated with commits (when available)
- Tag names

### LLM Evals

The LLM evaluation workflow sends only predefined test inputs from the golden set (`evals/golden_intent.json`). No user data or repository content is sent.

## What is Never Sent

The following data is never sent to external AI services:

- Repository secrets or credentials
- Environment variables containing sensitive data
- Personal data (PII)
- Full file contents (only diffs/patches of changed code)
- Binary files or non-text content

## Security Controls

### Redaction

All content is passed through `redact_secrets()` before being sent to OpenAI. This function detects and redacts:

- AWS access keys (`AKIA...`)
- GitHub tokens (`ghp_`, `ghs_`)
- OpenAI/Stripe API keys (`sk-...`)
- JWT tokens
- PEM private keys (RSA, EC, generic)
- OpenSSH private keys
- Bearer tokens
- Environment variable assignments with sensitive names (`API_KEY`, `SECRET`, `TOKEN`, `PASSWORD`, etc.)
- Generic long hex/base64 secrets

### Truncation

To prevent excessive API costs and reduce data exposure:

- PR diffs are truncated when they exceed size limits
- Commit history is limited to 50 commits per release

### Workflow Permissions

All AI workflows use least-privilege permissions:

- `contents: read` for reading code
- `pull-requests: write` only for workflows that post PR comments
- `contents: write` only for the release notes workflow (to create releases)

### Secret Masking

Workflows mask the `OPENAI_API_KEY` in logs using GitHub Actions' `::add-mask::` command to prevent accidental exposure.

## Disabling AI Features

To disable AI features in this repository:

1. **Remove the secret**: Delete `OPENAI_API_KEY` from repository secrets (Settings → Secrets and variables → Actions). Workflows will skip gracefully.

2. **Disable specific workflows**: Go to Actions → select workflow → "..." menu → "Disable workflow"

3. **Delete workflow files**: Remove the corresponding `.github/workflows/*.yml` files

## Cost Considerations

AI features use OpenAI's `gpt-4o-mini` model, which is cost-effective:

- PR summary: ~$0.001 per PR
- Test draft: ~$0.001 per PR
- Release notes: ~$0.001 per release
- LLM evals (10 cases): ~$0.001 per run

Estimated monthly cost for active development: < $1

## Compliance Notes

- No data is stored by OpenAI beyond API processing (per OpenAI's API data usage policy)
- All AI-generated content is clearly marked in PR comments
- Generated content is suggestions only; no automatic commits or merges
