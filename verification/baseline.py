"""Baseline testing before a repair."""

from .test_runner import run_tests


def run_baseline_tests(workspace_path: str, language: str) -> dict:
    """Return unchanged test results; failures can evidence a reproduced bug."""
    return run_tests(workspace_path, language)
