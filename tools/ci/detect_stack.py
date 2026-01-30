#!/usr/bin/env python3
"""Detect project stack from markers or explicit lock file.

Usage:
    python detect_stack.py [repo_root]

Returns the detected stack name (e.g., 'python-uv', 'node', 'go', 'java', 'none').
"""
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    # Fallback for environments without PyYAML
    yaml = None


def detect_stack(repo_root: Path) -> str:
    """Detect the project stack from markers or explicit lock file.

    Priority:
    1. Explicit lock file (tools/stack.yml)
    2. Marker file detection (order matters - first match wins)

    Args:
        repo_root: Path to the repository root

    Returns:
        Stack name string (e.g., 'python-uv', 'node', 'go', 'java', 'none')
    """
    # Priority 1: Explicit lock file
    stack_lock = repo_root / "tools" / "stack.yml"
    if stack_lock.exists():
        if yaml:
            with open(stack_lock) as f:
                config = yaml.safe_load(f)
                return config.get("stack", "none")
        else:
            # Simple fallback parser for stack.yml
            with open(stack_lock) as f:
                for line in f:
                    if line.strip().startswith("stack:"):
                        return line.split(":", 1)[1].strip().strip('"').strip("'")

    # Priority 2: Marker detection (order matters - first match wins)
    # More specific markers should come first
    markers = [
        ("uv.lock", "python-uv"),
        ("pyproject.toml", "python"),
        ("setup.py", "python"),
        ("requirements.txt", "python"),
        ("package.json", "node"),
        ("go.mod", "go"),
        ("pom.xml", "java"),
        ("build.gradle", "java"),
    ]
    for marker, stack in markers:
        if (repo_root / marker).exists():
            return stack

    return "none"


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(detect_stack(root))
