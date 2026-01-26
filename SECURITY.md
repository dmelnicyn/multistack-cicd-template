# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability in this repository:

1. **Do not** open a public issue
2. Open a [private security advisory](../../security/advisories/new) on GitHub
3. Or email the maintainer directly with details

Please include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Secret Management

### What Should Never Be Committed

- API keys (OpenAI, Stripe, AWS, etc.)
- Passwords or tokens
- Private keys (SSH, PEM, etc.)
- Database credentials
- `.env` files with real values

### How Secrets Are Stored

- **CI/CD secrets**: Use GitHub repository secrets (Settings → Secrets and variables → Actions)
- **Local development**: Use `.env` files (gitignored) or environment variables
- **OPENAI_API_KEY**: Stored in GitHub Secrets, never logged, masked in workflow output

### Pre-commit Protection

The `redact_secrets()` function in `tools/shared.py` provides defense-in-depth by detecting and redacting potential secrets before they're sent to external services.

## Dependency Updates

### Automated Updates

Dependabot is configured to monitor and update:

- **GitHub Actions**: Weekly updates for workflow dependencies
- **Python packages**: Weekly updates for pip/uv dependencies

### Manual Review

- Review Dependabot PRs promptly
- Check changelogs for breaking changes
- Run tests before merging dependency updates

### Pinned Versions

- GitHub Actions are pinned to major versions (e.g., `@v4`)
- Python dependencies are locked in `uv.lock`

## CI Security

### Workflow Permissions

All workflows follow the principle of least privilege:

| Workflow | Permissions |
|----------|-------------|
| CI | `contents: read` |
| AI PR Summary | `contents: read`, `pull-requests: write` |
| AI Test Draft | `contents: read`, `pull-requests: write` |
| Release Notes | `contents: write` |
| LLM Evals | `contents: read` |

### Additional Protections

- **Timeouts**: All jobs have explicit timeouts (5-15 minutes)
- **Concurrency**: Workflows use concurrency groups to prevent duplicate runs
- **Secret masking**: API keys are masked in logs using `::add-mask::`
- **Graceful degradation**: AI workflows skip gracefully if `OPENAI_API_KEY` is not configured

## AI Security

See [docs/ai-policy.md](docs/ai-policy.md) for details on:

- What data is sent to OpenAI
- Redaction and truncation controls
- How to disable AI features
