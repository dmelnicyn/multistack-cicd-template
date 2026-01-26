#!/usr/bin/env python3
"""LLM evaluation runner for golden set intent classification tests.

Loads test cases from evals/golden_intent.json and validates that the
intent classifier produces expected outputs. Exits non-zero if any test fails.

Usage:
    python tools/run_llm_evals.py

Environment:
    OPENAI_API_KEY: Required for running evals (skips gracefully if missing)
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_cicd_demo.ai.intent import classify_intent  # noqa: E402
from ai_cicd_demo.ai.openai_client import OpenAIError  # noqa: E402

# Configuration
PER_TEST_TIMEOUT_SECONDS = 30
TOTAL_TIMEOUT_SECONDS = 300  # 5 minutes
GOLDEN_FILE = Path(__file__).parent.parent / "evals" / "golden_intent.json"


class TimeoutError(Exception):
    """Raised when a test exceeds the timeout."""

    pass


def timeout_handler(signum: int, frame: Any) -> None:
    """Signal handler for test timeout."""
    raise TimeoutError("Test exceeded timeout")


def load_golden_tests() -> list[dict[str, Any]]:
    """Load golden test cases from JSON file."""
    if not GOLDEN_FILE.exists():
        print(f"::error::Golden file not found: {GOLDEN_FILE}")
        sys.exit(1)

    with open(GOLDEN_FILE) as f:
        tests = json.load(f)

    if not tests:
        print("::error::Golden file is empty")
        sys.exit(1)

    return tests


def run_single_test(test_case: dict[str, Any]) -> tuple[bool, str, str | None]:
    """Run a single test case with timeout.

    Returns:
        Tuple of (passed, actual_intent_or_error, notes)
    """
    input_text = test_case["input_text"]
    expected = test_case["expected_intent"]

    # Set up timeout (Unix only, gracefully skip on Windows)
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(PER_TEST_TIMEOUT_SECONDS)

    try:
        actual = classify_intent(input_text)

        # Cancel timeout
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)

        passed = actual == expected
        return passed, actual, None

    except TimeoutError:
        return False, f"TIMEOUT (>{PER_TEST_TIMEOUT_SECONDS}s)", None
    except (OpenAIError, ValueError) as e:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
        return False, f"ERROR: {e}", None
    except Exception as e:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
        return False, f"UNEXPECTED ERROR: {e}", None


def main() -> int:
    """Run all golden set tests and report results."""
    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("::notice::OPENAI_API_KEY not configured. Skipping LLM evals.")
        print("To run LLM evals locally, set OPENAI_API_KEY environment variable.")
        return 0  # Success - graceful skip

    print("=" * 60)
    print("LLM Intent Classification Evals")
    print("=" * 60)

    tests = load_golden_tests()
    print(f"\nLoaded {len(tests)} test cases from {GOLDEN_FILE.name}")
    print(f"Per-test timeout: {PER_TEST_TIMEOUT_SECONDS}s")
    print(f"Total timeout: {TOTAL_TIMEOUT_SECONDS}s")
    print("-" * 60)

    start_time = time.time()
    passed_count = 0
    failed_count = 0
    timed_out = False
    results: list[tuple[str, bool, str, str, str | None]] = []

    for test_case in tests:
        # Check total timeout
        elapsed = time.time() - start_time
        if elapsed > TOTAL_TIMEOUT_SECONDS:
            timed_out = True
            print(f"\n::error::Total timeout exceeded ({TOTAL_TIMEOUT_SECONDS}s)")
            break

        test_id = test_case["id"]
        expected = test_case["expected_intent"]

        passed, actual, error = run_single_test(test_case)

        if passed:
            status = "[PASS]"
            passed_count += 1
        else:
            status = "[FAIL]"
            failed_count += 1

        # Print result
        if passed:
            print(f"{status} {test_id}: {actual} == {expected}")
        else:
            print(f"{status} {test_id}: got {actual}, expected {expected}")

        results.append((test_id, passed, actual, expected, error))

    # Summary
    total_time = time.time() - start_time
    total = passed_count + failed_count
    print("-" * 60)
    print(f"\nResults: {passed_count}/{total} passed")
    print(f"Time: {total_time:.2f}s")

    if failed_count > 0:
        print("\nFailed tests:")
        for test_id, passed, actual, expected, _error in results:
            if not passed:
                print(f"  - {test_id}: got {actual}, expected {expected}")
        print(f"\n::error::{failed_count} LLM eval(s) failed")
        return 1

    if timed_out:
        print("\n::error::LLM evals aborted due to total timeout")
        return 1

    print("\nAll LLM evals passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
