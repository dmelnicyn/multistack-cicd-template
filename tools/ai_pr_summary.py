#!/usr/bin/env python3
"""AI-powered PR summary generator.

Fetches PR data from GitHub, redacts potential secrets, generates an AI summary
using OpenAI, and posts/updates a comment on the PR.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI

# Constants
COMMENT_MARKER = "<!-- ai-pr-summary-bot -->"
MAX_DIFF_SIZE = 50_000  # 50KB max diff size
MAX_PATCH_PER_FILE = 500  # chars per file when truncating
OPENAI_MODEL = "gpt-4o-mini"


def get_env_or_exit(name: str) -> str:
    """Get environment variable or exit with error."""
    value = os.environ.get(name)
    if not value:
        print(f"::error::Missing required environment variable: {name}")
        sys.exit(1)
    return value


def check_openai_key() -> str | None:
    """Check if OpenAI API key is configured. Returns key or None."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("::notice::OPENAI_API_KEY not configured. Skipping AI PR summary.")
        return None
    return key


def github_request(
    method: str,
    endpoint: str,
    github_token: str,
    json_data: dict[str, Any] | None = None,
) -> Any:
    """Make a request to GitHub API."""
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com{endpoint}"

    response = requests.request(
        method,
        url,
        headers=headers,
        json=json_data,
        timeout=30,
    )
    response.raise_for_status()

    if response.status_code == 204:
        return {}
    return response.json()


def fetch_pr_files_paginated(
    repo: str,
    pr_number: str,
    github_token: str,
) -> list[dict[str, Any]]:
    """Fetch all changed files with patches, handling pagination."""
    all_files: list[dict[str, Any]] = []
    page = 1

    while True:
        files: list[dict[str, Any]] = github_request(
            "GET",
            f"/repos/{repo}/pulls/{pr_number}/files?per_page=100&page={page}",
            github_token,
        )

        if not files:
            break

        all_files.extend(files)
        page += 1

    return all_files


def fetch_pr_data(repo: str, pr_number: str, github_token: str) -> dict[str, Any]:
    """Fetch PR metadata and changed files with patches."""
    # Get PR details
    pr = github_request("GET", f"/repos/{repo}/pulls/{pr_number}", github_token)

    # Get changed files with patches (paginated)
    files = fetch_pr_files_paginated(repo, pr_number, github_token)

    return {
        "title": pr.get("title", ""),
        "body": pr.get("body", "") or "",
        "files": files,
        "file_count": len(files),
    }


def redact_secrets(content: str) -> str:
    """Redact potential secrets from content using regex heuristics."""
    redacted = content

    # Pattern 1: AWS access keys (AKIA...)
    redacted = re.sub(r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]", redacted)

    # Pattern 2: Generic long tokens/keys (20+ alphanumeric chars after key-like words)
    redacted = re.sub(
        r"((?:api[_-]?key|secret|token|password|auth|credential|private[_-]?key)"
        r"[\s]*[:=][\s]*['\"]?)([A-Za-z0-9_\-]{20,})",
        r"\1[REDACTED]",
        redacted,
        flags=re.IGNORECASE,
    )

    # Pattern 3: Environment variable assignments with sensitive names
    redacted = re.sub(
        r"^(\s*(?:export\s+)?(?:API_KEY|SECRET|TOKEN|PASSWORD|AUTH|CREDENTIAL|"
        r"PRIVATE_KEY|ACCESS_KEY|DATABASE_URL|DB_PASSWORD)[A-Z_]*\s*=\s*).+$",
        r"\1[REDACTED]",
        redacted,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # Pattern 4: Bearer tokens
    redacted = re.sub(
        r"(Bearer\s+)[A-Za-z0-9_\-\.]{20,}",
        r"\1[REDACTED]",
        redacted,
        flags=re.IGNORECASE,
    )

    # Pattern 5: GitHub tokens
    redacted = re.sub(
        r"(gh[ps]_)[A-Za-z0-9]{36,}",
        r"\1[REDACTED]",
        redacted,
    )

    # Pattern 6: Generic hex/base64 secrets (40+ chars)
    redacted = re.sub(
        r"(['\"])[A-Fa-f0-9]{40,}\1",
        r'"[REDACTED_HEX]"',
        redacted,
    )

    # Pattern 7: sk-... API keys (OpenAI, Stripe, etc.)
    # Handles sk-proj-..., sk-live-..., sk-test-..., sk-...
    redacted = re.sub(
        r"sk-[A-Za-z0-9_-]{20,}",
        "[REDACTED_SK_KEY]",
        redacted,
    )

    # Pattern 8: JWT-like tokens (three base64url segments separated by dots)
    # Base64url: [A-Za-z0-9_-]+ (at least 10 chars per segment to avoid false positives)
    redacted = re.sub(
        r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        "[REDACTED_JWT]",
        redacted,
    )

    # Pattern 9: PEM private key blocks
    redacted = re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
        "[REDACTED_PEM_KEY]",
        redacted,
    )

    return redacted


def truncate_diff(files: list[dict[str, Any]]) -> tuple[str, bool]:
    """Truncate diff content if too large. Returns (content, was_truncated)."""
    # Build full diff first
    full_diff_parts = []
    for file_info in files:
        filename = file_info.get("filename", "unknown")
        patch = file_info.get("patch", "")
        if patch:
            full_diff_parts.append(f"### {filename}\n```diff\n{patch}\n```\n")
        else:
            note = "*(no patch available; possibly binary or too large)*"
            full_diff_parts.append(f"### {filename}\n{note}\n")

    full_diff = "\n".join(full_diff_parts)

    # Check if within limits
    if len(full_diff) <= MAX_DIFF_SIZE:
        return full_diff, False

    # Truncate: show file list + truncated patches
    truncated_parts = ["**Note: Diff truncated due to size.**\n"]

    for file_info in files:
        filename = file_info.get("filename", "unknown")
        status = file_info.get("status", "modified")
        additions = file_info.get("additions", 0)
        deletions = file_info.get("deletions", 0)
        patch = file_info.get("patch", "")

        if patch:
            truncated_parts.append(
                f"- `{filename}` ({status}: +{additions}/-{deletions})"
            )
            truncated_patch = patch[:MAX_PATCH_PER_FILE]
            if len(patch) > MAX_PATCH_PER_FILE:
                truncated_patch += "\n... (truncated)"
            truncated_parts.append(f"```diff\n{truncated_patch}\n```\n")
        else:
            truncated_parts.append(
                f"- `{filename}` ({status}: +{additions}/-{deletions}) "
                "*(no patch available; possibly binary or too large)*"
            )

    return "\n".join(truncated_parts), True


def group_files_by_area(files: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Group files by area based on path patterns."""
    areas: dict[str, list[str]] = {
        "Tests": [],
        "Configuration": [],
        "Documentation": [],
        "CI/CD": [],
        "Source": [],
        "Other": [],
    }

    for file_info in files:
        filename = file_info.get("filename", "")

        if filename.startswith("tests/") or filename.startswith("test_"):
            areas["Tests"].append(filename)
        elif filename.startswith(".github/"):
            areas["CI/CD"].append(filename)
        elif filename.endswith((".md", ".rst", ".txt")):
            areas["Documentation"].append(filename)
        elif filename in (
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "Makefile",
            ".gitignore",
            "uv.lock",
        ) or filename.endswith((".yml", ".yaml", ".toml", ".ini", ".cfg")):
            areas["Configuration"].append(filename)
        elif filename.startswith("src/") or filename.endswith(".py"):
            areas["Source"].append(filename)
        else:
            areas["Other"].append(filename)

    # Remove empty areas
    return {k: v for k, v in areas.items() if v}


def load_prompt_template() -> str:
    """Load prompt template from file."""
    script_dir = Path(__file__).parent.parent
    template_path = script_dir / "prompts" / "pr_summary.md"

    if not template_path.exists():
        print(f"::warning::Prompt template not found at {template_path}")
        # Fallback template
        return """You are a code review assistant. Analyze the following PR and provide:

1. **Summary** - Bullet points of key changes (max 5-7 points)
2. **Risk Level** - Low/Medium/High with brief reasons
3. **Suggested Checks** - Tests or manual checks based on changes
4. **Files Changed** - Grouped by area

## PR Information
- **Title**: {title}
- **Description**: {body}
- **Files Changed**: {file_count}

## Changes
{diff_content}

Respond in markdown format suitable for a GitHub comment."""

    return template_path.read_text()


def build_prompt(pr_data: dict[str, Any], diff_content: str) -> str:
    """Build the prompt from template and PR data."""
    template = load_prompt_template()

    return template.format(
        title=pr_data["title"],
        body=pr_data["body"] or "(No description provided)",
        file_count=pr_data["file_count"],
        diff_content=diff_content,
    )


def call_openai(prompt: str, api_key: str) -> str:
    """Call OpenAI API to generate PR summary."""
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful code review assistant. "
                    "Provide concise, actionable PR summaries."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=1500,
        temperature=0.3,
    )

    return response.choices[0].message.content or ""


def find_existing_comment(
    repo: str,
    pr_number: str,
    github_token: str,
) -> int | None:
    """Find existing bot comment by marker. Returns comment ID or None."""
    comments: list[dict[str, Any]] = github_request(
        "GET",
        f"/repos/{repo}/issues/{pr_number}/comments",
        github_token,
    )

    for comment in comments:
        body = comment.get("body", "")
        if COMMENT_MARKER in body:
            comment_id = comment.get("id")
            return int(comment_id) if comment_id is not None else None

    return None


def post_or_update_comment(
    repo: str,
    pr_number: str,
    github_token: str,
    content: str,
) -> None:
    """Post a new comment or update existing one."""
    # Add marker to content
    full_content = f"{COMMENT_MARKER}\n\n{content}"

    existing_id = find_existing_comment(repo, pr_number, github_token)

    if existing_id:
        # Update existing comment
        github_request(
            "PATCH",
            f"/repos/{repo}/issues/comments/{existing_id}",
            github_token,
            json_data={"body": full_content},
        )
        print(f"Updated existing comment {existing_id}")
    else:
        # Create new comment
        github_request(
            "POST",
            f"/repos/{repo}/issues/{pr_number}/comments",
            github_token,
            json_data={"body": full_content},
        )
        print("Created new PR comment")


def main() -> None:
    """Main entry point."""
    # Check for OpenAI key first (graceful skip if missing)
    openai_key = check_openai_key()
    if not openai_key:
        sys.exit(0)

    # Get required environment variables
    github_token = get_env_or_exit("GITHUB_TOKEN")
    pr_number = get_env_or_exit("PR_NUMBER")
    repo = get_env_or_exit("REPO")

    print(f"Generating AI summary for PR #{pr_number} in {repo}")

    # Fetch PR data
    pr_data = fetch_pr_data(repo, pr_number, github_token)
    print(f"Fetched PR: {pr_data['title']} ({pr_data['file_count']} files)")

    # Process diff content
    diff_content, was_truncated = truncate_diff(pr_data["files"])
    if was_truncated:
        print("::notice::Diff was truncated due to size")

    # Redact potential secrets
    diff_content = redact_secrets(diff_content)
    pr_body = redact_secrets(pr_data["body"])
    pr_data["body"] = pr_body

    # Build prompt
    prompt = build_prompt(pr_data, diff_content)

    # Call OpenAI
    print("Calling OpenAI API...")
    summary = call_openai(prompt, openai_key)

    # Post or update comment
    post_or_update_comment(repo, pr_number, github_token, summary)
    print("Done!")


if __name__ == "__main__":
    main()
