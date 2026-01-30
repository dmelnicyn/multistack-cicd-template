#!/usr/bin/env python3
"""AI-powered draft unit test generator.

Analyzes changed Python files in a PR, generates draft pytest test suggestions
using OpenAI, outputs to an artifact file, and posts a summary comment on the PR.
"""

from __future__ import annotations

import fnmatch
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
COMMENT_MARKER = "<!-- ai-test-draft-bot -->"
MAX_PATCH_PER_FILE = 2000  # chars per file for context
MAX_TOTAL_CONTEXT = 30_000  # max total chars to send to OpenAI
OPENAI_MODEL = "gpt-4o-mini"
ARTIFACT_PATH = "artifacts/draft_tests.md"

# File filtering patterns
INCLUDE_PATTERNS = ["src/**/*.py"]
EXCLUDE_PATTERNS = [
    "**/venv/**",
    "**/.venv/**",
    "**/*.lock",
    "**/*.md",
    "**/test_*.py",
    "**/tests/**",
    "**/__pycache__/**",
    "**/conftest.py",
]


def matches_pattern(filename: str, patterns: list[str]) -> bool:
    """Check if filename matches any of the glob patterns."""
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def filter_relevant_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter files to only include relevant Python source files."""
    relevant = []

    for file_info in files:
        filename = file_info.get("filename", "")

        # Check if it matches include patterns
        if not matches_pattern(filename, INCLUDE_PATTERNS):
            continue

        # Check if it matches exclude patterns
        if matches_pattern(filename, EXCLUDE_PATTERNS):
            continue

        # Must be a Python file
        if not filename.endswith(".py"):
            continue

        relevant.append(file_info)

    return relevant


def build_file_context(files: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Build context string from files with patches. Returns (context, file_list)."""
    context_parts = []
    file_list = []
    total_chars = 0
    files_processed = 0

    for file_info in files:
        filename = file_info.get("filename", "unknown")
        patch = file_info.get("patch", "")
        status = file_info.get("status", "modified")
        additions = file_info.get("additions", 0)
        deletions = file_info.get("deletions", 0)

        # Build file section
        file_section = f"### {filename}\n"
        file_section += f"**Status**: {status} (+{additions}/-{deletions})\n\n"

        if patch:
            # Truncate patch if too large
            if len(patch) > MAX_PATCH_PER_FILE:
                patch = patch[:MAX_PATCH_PER_FILE] + "\n... (truncated)"

            # Redact secrets from patch
            patch = redact_secrets(patch)
            file_section += f"```diff\n{patch}\n```\n"
        else:
            file_section += "*(no patch available; possibly binary or too large)*\n"

        # Check if adding this would exceed total limit
        if total_chars + len(file_section) > MAX_TOTAL_CONTEXT:
            remaining = len(files) - files_processed
            context_parts.append(
                f"\n**Note:** {remaining} additional files "
                "omitted due to size constraints.\n"
            )
            break

        context_parts.append(file_section)
        file_list.append(filename)
        total_chars += len(file_section)
        files_processed += 1

    return "\n".join(context_parts), file_list


def load_prompt_template() -> str:
    """Load prompt template from file."""
    script_dir = Path(__file__).parent.parent
    template_path = script_dir / "prompts" / "test_generation.md"

    if not template_path.exists():
        print(f"::warning::Prompt template not found at {template_path}")
        # Fallback template
        return (
            "You are a test generation assistant. "
            "Analyze the code changes and generate draft pytest tests.\n\n"
            "## PR Information\n"
            "- **Title**: {pr_title}\n"
            "- **Files Changed**: {file_count}\n\n"
            "## Files to Test\n{file_list}\n\n"
            "## Code Changes\n{file_details}\n\n"
            "For each file, provide:\n"
            "1. Test file path suggestion\n"
            "2. What to test (functions, classes, edge cases)\n"
            "3. Draft pytest code blocks\n"
            "4. Notes on testability (hard-to-test code, suggested refactors)\n\n"
            "Respond in markdown format."
        )

    return template_path.read_text()


def build_prompt(
    pr_data: dict[str, Any], file_context: str, file_list: list[str]
) -> str:
    """Build the prompt from template and PR data."""
    template = load_prompt_template()

    return template.format(
        pr_title=pr_data["title"],
        file_count=len(file_list),
        file_list="\n".join(f"- `{f}`" for f in file_list),
        file_details=file_context,
    )


def call_openai(prompt: str, api_key: str) -> str:
    """Call OpenAI API to generate test suggestions."""
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert Python testing assistant. "
                    "Generate high-quality, practical pytest test suggestions. "
                    "Focus on testing behavior, edge cases, and error handling. "
                    "Use clear test names following "
                    "test_<function>_<scenario> convention."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=3000,
        temperature=0.3,
    )

    return response.choices[0].message.content or ""


def write_artifact(
    pr_data: dict[str, Any],
    file_list: list[str],
    full_output: str,
) -> None:
    """Write the full output to the artifact file."""
    artifact_path = Path(ARTIFACT_PATH)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    files_list = chr(10).join(f"- `{f}`" for f in file_list)
    footer = (
        "*Generated by AI Test Draft Bot. "
        "These are suggestions only - review and adapt before use.*"
    )
    content = f"""# Draft Test Suggestions

## PR: {pr_data["title"]}

**Files analyzed:** {len(file_list)}

### Files Touched
{files_list}

---

{full_output}

---

{footer}
"""

    artifact_path.write_text(content)
    print(f"Wrote artifact to {ARTIFACT_PATH}")


def build_comment_summary(
    pr_data: dict[str, Any],
    file_list: list[str],
    full_output: str,
) -> str:
    """Build a concise PR comment from the full output."""
    # Extract first few test suggestions for the comment
    lines = full_output.split("\n")

    # Find code blocks (test suggestions) - match ```python or ```py
    code_blocks = []
    in_block = False
    current_block: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```python") or stripped.startswith("```py"):
            in_block = True
            current_block = [line]
        elif stripped == "```" and in_block:
            current_block.append(line)
            code_blocks.append("\n".join(current_block))
            in_block = False
            current_block = []
        elif in_block:
            current_block.append(line)

    # Build comment
    comment = f"""## 🧪 Draft Test Suggestions

**PR:** {pr_data["title"]}
**Files analyzed:** {len(file_list)}

### Files Covered
"""

    # List files (max 10)
    for f in file_list[:10]:
        comment += f"- `{f}`\n"
    if len(file_list) > 10:
        comment += f"- ... and {len(file_list) - 10} more\n"

    comment += "\n### Sample Test Suggestions\n\n"

    # Include up to 2 code blocks (or a truncated preview)
    if code_blocks:
        for block in code_blocks[:2]:
            # Truncate very long blocks
            if len(block) > 800:
                block_lines = block.split("\n")
                truncated = "\n".join(block_lines[:20])
                if not truncated.endswith("```"):
                    truncated += "\n# ... (truncated)\n```"
                comment += truncated + "\n\n"
            else:
                comment += block + "\n\n"
    else:
        # If no code blocks found, show first ~40 lines of output
        preview_lines = lines[:40]
        preview = "\n".join(preview_lines)
        if len(lines) > 40:
            preview += "\n\n... (see artifact for full output)"
        comment += preview

    comment += """
---

📦 **Full output available in workflow artifacts** (`draft_tests.md`)

*These are AI-generated suggestions. Review and adapt before adding to your test suite.*
"""

    return comment


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

    print(f"Generating draft tests for PR #{pr_number} in {repo}")

    # Fetch PR data
    pr_data = fetch_pr_data(repo, pr_number, github_token)
    print(f"Fetched PR: {pr_data['title']} ({pr_data['file_count']} files)")

    # Filter to relevant Python source files
    relevant_files = filter_relevant_files(pr_data["files"])
    print(f"Found {len(relevant_files)} relevant Python source files")

    if not relevant_files:
        print(
            "::notice::No relevant Python source files found. Skipping test generation."
        )
        # Still post a comment to inform
        comment = (
            "## 🧪 Draft Test Suggestions\n\n"
            "No Python source files under `src/` were changed in this PR. "
            "Test generation skipped."
        )
        post_or_update_comment(repo, pr_number, github_token, comment, COMMENT_MARKER)
        sys.exit(0)

    # Build file context
    file_context, file_list = build_file_context(relevant_files)

    # Build prompt
    prompt = build_prompt(pr_data, file_context, file_list)

    # Call OpenAI
    print("Calling OpenAI API...")
    full_output = call_openai(prompt, openai_key)

    # Write artifact
    write_artifact(pr_data, file_list, full_output)

    # Build and post comment
    comment = build_comment_summary(pr_data, file_list, full_output)
    post_or_update_comment(repo, pr_number, github_token, comment, COMMENT_MARKER)

    print("Done!")


if __name__ == "__main__":
    main()
