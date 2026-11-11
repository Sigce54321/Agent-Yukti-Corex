"""Verify repair outcomes from existing test results."""


def verify_fix(baseline_result: dict, regression_result: dict) -> dict:
    """Require a reproduced baseline failure followed by passing regression."""
    passed = False
    if not isinstance(baseline_result, dict) or not isinstance(regression_result, dict):
        summary = "Verification failed: baseline and regression must be dictionaries."
    else:
        baseline_status = baseline_result.get("test_status")
        regression_status = regression_result.get("test_status")
        valid_statuses = ("passed", "failed", "error", "not_run")
        if (
            not isinstance(baseline_status, str)
            or not isinstance(regression_status, str)
            or baseline_status not in valid_statuses
            or regression_status not in valid_statuses
        ):
            summary = "Verification failed: missing or invalid test status."
        elif baseline_status == "passed":
            summary = "Verification failed: baseline passed, so the original bug was not reproduced."
        elif baseline_status in ("error", "not_run"):
            summary = f"Verification failed: baseline status is {baseline_status}; reproduction is unconfirmed."
        elif regression_status in ("error", "not_run"):
            summary = f"Verification failed: regression status is {regression_status}; the repair is unconfirmed."
        elif regression_status == "failed":
            summary = "Verification failed: regression tests still fail after repair."
        else:
            passed = True
            summary = "Fix verified: baseline reproduced the bug and regression tests passed."

    return {
        "passed": passed,
        "summary": summary,
        "baseline": baseline_result,
        "regression": regression_result,
    }
