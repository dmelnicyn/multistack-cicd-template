#!/usr/bin/env python3
"""Select CI commands for a given stack from tooling matrix.

Usage:
    python select_commands.py <stack>

Outputs JSON with stack configuration and commands.
"""
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def load_matrix(matrix_path: Path) -> dict:
    """Load tooling matrix from YAML file.

    Args:
        matrix_path: Path to tooling-matrix.yml

    Returns:
        Parsed matrix dictionary
    """
    if yaml:
        with open(matrix_path) as f:
            return yaml.safe_load(f)

    # Simple fallback parser for basic YAML structure
    # Only handles the specific structure of tooling-matrix.yml
    result = {"stacks": {}}
    current_stack = None
    current_section = None

    with open(matrix_path) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(line.lstrip())

            if indent == 2 and stripped.endswith(":"):
                # Stack name
                current_stack = stripped[:-1]
                result["stacks"][current_stack] = {"commands": {}}
            elif indent == 4 and current_stack:
                if stripped == "commands:":
                    current_section = "commands"
                elif stripped.startswith("markers:"):
                    current_section = None
                    # Parse inline array
                    val = stripped.split(":", 1)[1].strip()
                    if val.startswith("["):
                        markers = [
                            m.strip().strip('"').strip("'")
                            for m in val[1:-1].split(",")
                            if m.strip()
                        ]
                        result["stacks"][current_stack]["markers"] = markers
                elif ":" in stripped:
                    key, val = stripped.split(":", 1)
                    val = val.strip().strip('"').strip("'")
                    result["stacks"][current_stack][key] = val
                    current_section = None
            elif indent == 6 and current_stack and current_section == "commands":
                if ":" in stripped:
                    key, val = stripped.split(":", 1)
                    val = val.strip().strip('"').strip("'")
                    result["stacks"][current_stack]["commands"][key] = val

    return result


def select_commands(stack: str, matrix_path: Path) -> dict:
    """Select CI commands for a given stack.

    Args:
        stack: Stack name (e.g., 'python-uv', 'node')
        matrix_path: Path to tooling-matrix.yml

    Returns:
        Dictionary with stack configuration and skip_ci flag
    """
    matrix = load_matrix(matrix_path)

    stack_config = matrix.get("stacks", {}).get(stack)
    if not stack_config:
        # Fall back to 'none' stack if unknown
        stack_config = matrix.get("stacks", {}).get("none", {})
        stack = "none"

    # Determine if CI should be skipped (pre-activation state)
    skip_ci = stack == "none" or stack_config.get("setup_action") == "none"

    return {
        "stack": stack,
        "skip_ci": skip_ci,
        "setup_action": stack_config.get("setup_action", ""),
        "default_version": stack_config.get("default_version", ""),
        **stack_config.get("commands", {}),
    }


if __name__ == "__main__":
    stack = sys.argv[1] if len(sys.argv) > 1 else "none"
    matrix_path = Path(__file__).parent.parent / "tooling-matrix.yml"
    result = select_commands(stack, matrix_path)
    print(json.dumps(result))
