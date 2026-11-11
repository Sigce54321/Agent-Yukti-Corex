"""Regression testing after a repair."""

from .test_runner import run_tests


def run_regression_tests(workspace_path: str, language: str) -> dict:
    """Return unchanged test results, preserving failures and sandbox errors."""
    return run_tests(workspace_path, language)
