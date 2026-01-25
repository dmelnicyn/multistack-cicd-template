#!/usr/bin/env python3
"""Shared utilities for AI-powered CI/CD tools.

Contains reusable functions for GitHub API interactions, secret redaction,
and PR comment management.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any

import requests


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
        print("::notice::OPENAI_API_KEY not configured. Skipping AI processing.")
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


def github_request_with_headers(
    method: str,
    endpoint: str,
    github_token: str,
    json_data: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    """Make a request to GitHub API with custom headers.

    Allows overriding or adding headers for endpoints that require specific
    Accept headers (e.g., /commits/{sha}/pulls).
    """
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if extra_headers:
        headers.update(extra_headers)

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
    """Fetch all changed files with patches, handling pagination.

    Paginates through /pulls/{pr}/files using per_page=100 until empty response.
    """
    all_files: list[dict[str, Any]] = []
    page = 1

    # Paginate: fetch 100 files per request, continue until empty response
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


def find_existing_comment(
    repo: str,
    pr_number: str,
    github_token: str,
    marker: str,
) -> int | None:
    """Find existing bot comment by marker. Returns comment ID or None."""
    comments: list[dict[str, Any]] = github_request(
        "GET",
        f"/repos/{repo}/issues/{pr_number}/comments",
        github_token,
    )

    for comment in comments:
        body = comment.get("body", "")
        if marker in body:
            comment_id = comment.get("id")
            return int(comment_id) if comment_id is not None else None

    return None


def post_or_update_comment(
    repo: str,
    pr_number: str,
    github_token: str,
    content: str,
    marker: str,
) -> None:
    """Post a new comment or update existing one."""
    # Add marker to content
    full_content = f"{marker}\n\n{content}"

    existing_id = find_existing_comment(repo, pr_number, github_token, marker)

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
