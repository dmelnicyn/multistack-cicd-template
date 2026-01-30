#!/usr/bin/env python3
"""AI-powered PR summary generator.

Fetches PR data from GitHub, redacts potential secrets, generates an AI summary
using OpenAI, and posts/updates a comment on the PR.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from openai import OpenAI
from shared import (
    check_openai_key,
    fetch_pr_data,
    get_env_or_exit,
    post_or_update_comment,
    redact_secrets,
)

# Constants
COMMENT_MARKER = "<!-- ai-pr-summary-bot -->"
MAX_DIFF_SIZE = 50_000  # 50KB max diff size
MAX_PATCH_PER_FILE = 500  # chars per file when truncating
OPENAI_MODEL = "gpt-4o-mini"


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
    post_or_update_comment(repo, pr_number, github_token, summary, COMMENT_MARKER)
    print("Done!")


if __name__ == "__main__":
    main()
