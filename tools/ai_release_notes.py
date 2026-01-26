#!/usr/bin/env python3
"""AI-powered release notes generator.

Fetches commits between tags from GitHub, generates release notes using OpenAI,
and creates/updates a draft release on GitHub.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests
from openai import OpenAI
from shared import (
    check_openai_key,
    get_env_or_exit,
    github_request,
    github_request_with_headers,
    redact_secrets,
)

# Constants
OPENAI_MODEL = "gpt-4o-mini"
MAX_COMMITS = 50  # Cap to limit API calls


def get_tags(repo: str, github_token: str) -> list[dict[str, Any]]:
    """Fetch all tags from repository."""
    tags: list[dict[str, Any]] = github_request(
        "GET",
        f"/repos/{repo}/tags?per_page=100",
        github_token,
    )
    return tags


def get_previous_tag(
    repo: str, current_tag: str, github_token: str
) -> str | None:
    """Find the tag immediately before current_tag.

    Tags are returned by GitHub in order of their commit date (newest first).
    We find the current tag and return the next one in the list.
    """
    tags = get_tags(repo, github_token)

    found_current = False
    for tag in tags:
        tag_name = tag.get("name", "")
        if tag_name == current_tag:
            found_current = True
            continue
        if found_current:
            return tag_name

    return None


def get_commits_between(
    repo: str, base: str | None, head: str, github_token: str
) -> tuple[list[dict[str, Any]], int]:
    """Get commits between two refs using compare API.

    If base is None (first release), get commits from the beginning.
    Returns (commits capped to MAX_COMMITS, total_count).
    """
    if base:
        # Use compare endpoint
        compare_data: dict[str, Any] = github_request(
            "GET",
            f"/repos/{repo}/compare/{base}...{head}",
            github_token,
        )
        commits: list[dict[str, Any]] = compare_data.get("commits", [])
        # Use total_commits from API if available, else fall back to len
        total_count = compare_data.get("total_commits", len(commits))
    else:
        # First release: get recent commits up to the tag
        commits = github_request(
            "GET",
            f"/repos/{repo}/commits?sha={head}&per_page={MAX_COMMITS}",
            github_token,
        )
        # For first release, we only know about commits returned (already capped)
        total_count = len(commits)

    return commits[:MAX_COMMITS], total_count


def get_pr_for_commit(
    repo: str, sha: str, github_token: str
) -> dict[str, Any] | None:
    """Get associated PR for a commit, if any.

    Uses the /commits/{sha}/pulls endpoint. Retries once with alternative
    Accept header if the first attempt fails.
    Returns the first (most relevant) PR or None if no PR is associated.
    """
    endpoint = f"/repos/{repo}/commits/{sha}/pulls"
    accept_headers = [
        "application/vnd.github+json",
        "application/json",  # Fallback
    ]

    for accept in accept_headers:
        try:
            prs: list[dict[str, Any]] = github_request_with_headers(
                "GET",
                endpoint,
                github_token,
                extra_headers={"Accept": accept},
            )
            if prs:
                return prs[0]  # Return the first/most relevant PR
            return None  # Empty list means no associated PR
        except requests.HTTPError:
            continue  # Try next Accept header

    return None


def build_changes_list(
    commits: list[dict[str, Any]], repo: str, github_token: str
) -> str:
    """Build formatted changes list with PR titles where available.

    Returns changes_text.
    """
    changes: list[str] = []

    for commit in commits:
        sha = commit.get("sha", "")
        commit_data = commit.get("commit", {})
        message = commit_data.get("message", "")
        # Get first line of commit message
        subject = message.split("\n")[0].strip()

        # Try to get associated PR
        pr = get_pr_for_commit(repo, sha, github_token)
        if pr:
            pr_title = pr.get("title", "")
            pr_number = pr.get("number", "")
            if pr_title and pr_number:
                changes.append(f"- {pr_title} (#{pr_number})")
                continue

        # Fallback to commit message
        if subject:
            changes.append(f"- {subject}")

    return "\n".join(changes)


def load_prompt_template() -> str:
    """Load prompt template from file."""
    script_dir = Path(__file__).parent.parent
    template_path = script_dir / "prompts" / "release_notes.md"

    if not template_path.exists():
        print(f"::warning::Prompt template not found at {template_path}")
        # Fallback template
        return """Generate release notes for version {tag}.

Group changes into: Features, Fixes, Documentation, Chore/CI, Other.
Highlight any breaking changes.

{first_release_note}

## Changes

{changes}

Output clean markdown release notes."""

    return template_path.read_text()


def build_prompt(
    tag: str, changes: str, omitted: int, is_first_release: bool
) -> str:
    """Build the prompt from template and release data."""
    template = load_prompt_template()

    first_release_note = ""
    if is_first_release:
        first_release_note = (
            "**Note:** This is the first release. "
            "Include all listed changes in the notes."
        )
    elif omitted > 0:
        first_release_note = (
            f"**Note:** {omitted} additional commits were omitted due to size limits."
        )

    return template.format(
        tag=tag,
        changes=changes,
        first_release_note=first_release_note,
    )


def call_openai(prompt: str, api_key: str) -> str:
    """Call OpenAI API to generate release notes."""
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a release notes writer. "
                    "Generate concise, user-facing release notes."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=2000,
        temperature=0.3,
    )

    return response.choices[0].message.content or ""


def get_release_for_tag(
    repo: str, tag: str, github_token: str
) -> dict[str, Any] | None:
    """Check if a release exists for the given tag (including drafts).

    Returns the release data or None if not found.

    Note: The /releases/tags/{tag} endpoint only returns published releases,
    not drafts. We must list all releases and filter by tag_name.
    """
    try:
        releases: list[dict[str, Any]] = github_request(
            "GET",
            f"/repos/{repo}/releases?per_page=100",
            github_token,
        )
        for release in releases:
            if release.get("tag_name") == tag:
                return release
    except requests.HTTPError:
        pass
    return None


def create_or_update_release(
    repo: str, tag: str, body: str, github_token: str
) -> None:
    """Create draft release or update existing one (idempotent)."""
    existing = get_release_for_tag(repo, tag, github_token)

    if existing:
        # Update existing release
        release_id = existing.get("id")
        github_request(
            "PATCH",
            f"/repos/{repo}/releases/{release_id}",
            github_token,
            json_data={
                "body": body,
                "draft": True,
            },
        )
        print(f"Updated existing release for {tag}")
    else:
        # Create new draft release
        github_request(
            "POST",
            f"/repos/{repo}/releases",
            github_token,
            json_data={
                "tag_name": tag,
                "name": tag,
                "body": body,
                "draft": True,
            },
        )
        print(f"Created draft release for {tag}")


def save_release_notes(content: str) -> None:
    """Save release notes to artifacts directory."""
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)

    output_path = artifacts_dir / "release_notes.md"
    output_path.write_text(content)
    print(f"Saved release notes to {output_path}")


def main() -> None:
    """Main entry point."""
    # Check for OpenAI key first (graceful skip if missing)
    openai_key = check_openai_key()
    if not openai_key:
        return

    # Get required environment variables
    github_token = get_env_or_exit("GITHUB_TOKEN")
    repo = get_env_or_exit("REPO")
    tag = get_env_or_exit("TAG")

    print(f"Generating release notes for {tag} in {repo}")

    # Determine previous tag
    previous_tag = get_previous_tag(repo, tag, github_token)
    is_first_release = previous_tag is None

    if is_first_release:
        print("No previous tag found - this is the first release")
    else:
        print(f"Previous tag: {previous_tag}")

    # Get commits between tags
    commits, total_count = get_commits_between(repo, previous_tag, tag, github_token)
    omitted = max(0, total_count - len(commits))
    print(f"Found {total_count} commits (processing {len(commits)})")

    if not commits:
        print("::warning::No commits found between tags")
        body = f"## {tag}\n\nNo changes detected."
        create_or_update_release(repo, tag, body, github_token)
        save_release_notes(body)
        return

    if omitted > 0:
        print(f"::notice::{omitted} commits omitted due to size limits")

    # Build changes list with PR titles
    changes = build_changes_list(commits, repo, github_token)

    # Redact potential secrets
    changes = redact_secrets(changes)

    # Build prompt
    prompt = build_prompt(tag, changes, omitted, is_first_release)

    # Call OpenAI
    print("Calling OpenAI API...")
    release_notes = call_openai(prompt, openai_key)

    # Create or update release
    create_or_update_release(repo, tag, release_notes, github_token)

    # Save to file for artifact upload
    save_release_notes(release_notes)

    print("Done!")


if __name__ == "__main__":
    main()
