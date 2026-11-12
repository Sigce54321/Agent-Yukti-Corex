
import core.workflow as workflow


ORIGINAL_CODE = """def divide(a, b):
    return a / b
"""

BUGGY_FRAGMENT = "return a / b"

FIXED_CODE = """def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
"""


def prepare_workflow(
    monkeypatch,
    tmp_path,
    regression_outcomes,
    challenger_verdict="APPROVE"
):
    """Prepare an isolated workflow with mocked external modules."""

    records_dir = tmp_path / "task_records"
    records_dir.mkdir()

    repository_dir = tmp_path / "repository"
    repository_dir.mkdir()

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    monkeypatch.setattr(
        workflow,
        "TASK_RECORDS_DIR",
        records_dir
    )

    monkeypatch.setattr(workflow, "TASKS", {})

    monkeypatch.setattr(
        workflow,
        "_repository_summary",
        lambda path: {
            "repository_path": str(path),
            "files": [{
                "file_path": "calculator.py",
                "content": ORIGINAL_CODE
            }],
            "file_count": 1
        }
    )

    task_id = "task-123456abcdef"

    workflow._save_task({
        "task_id": task_id,
        "repo_url": "https://github.com/example/calculator",
        "issue_number": 1,
        "status": "pending",
        "stage": "queued",
        "progress_percent": 0,
        "message": "Debugging task accepted.",
        "error": None
    })

    state = {
        "current_code": ORIGINAL_CODE,
        "repair_calls": 0,
        "regression_calls": 0,
        "challenge_calls": 0,
        "patch_calls": 0,
        "restore_calls": 0,
        "repair_feedback": []
    }

    def fake_call(module_name, function_name, *args, **kwargs):

        # GitHub issue reader
        if module_name == "github.issue_reader":
            return {
                "success": True,
                "number": 1,
                "title": "Handle division by zero",
                "body": "The divide function should handle zero.",
                "issue_url": (
                    "https://github.com/example/calculator/issues/1"
                )
            }

        # Repository cloning
        if (
            module_name == "github.repo_manager"
            and function_name == "clone_repository"
        ):
            return {
                "success": True,
                "repository_path": str(repository_dir),
                "default_branch": "main",
                "commit_sha": "original-commit"
            }

        # Separate working copy
        if (
            module_name == "github.repo_manager"
            and function_name == "create_working_copy"
        ):
            return {
                "success": True,
                "workspace_path": str(workspace_dir)
            }

        # Language detection
        if module_name == "languages.language_detector":
            return "python"

        # Docker availability
        if module_name == "sandbox.docker_manager":
            return True

        # Baseline testing
        if module_name == "verification.baseline":
            return {
                "test_status": "failed",
                "passed": False,
                "logs": "Baseline bug reproduced."
            }

        # Issue Analyzer
        if module_name == "agents.issue_analyzer":
            return {
                "problem_summary": "Division by zero is not handled."
            }

        # Bug Locator
        if module_name == "agents.bug_locator":
            return {
                "found": True,
                "file_path": "calculator.py",
                "function_name": "divide",
                "original_code": BUGGY_FRAGMENT,
                "reason": "Division by zero is not handled."
            }

        # Repair Agent
        if module_name == "agents.repair_agent":
            state["repair_calls"] += 1

            issue_analysis = args[1]

            state["repair_feedback"].append(
                issue_analysis.get("previous_attempt_feedback")
            )

            return {
                "file_path": "calculator.py",
                "original_code": BUGGY_FRAGMENT,
                "repository_code": ORIGINAL_CODE,
                "modified_code": FIXED_CODE
            }

        # Fix Challenger
        if module_name == "agents.fix_challenger":
            state["challenge_calls"] += 1

            issue_analysis_text = args[0]
            bug_location_text = args[1]
            repository_code = args[2]
            proposed_patch = args[3]

            assert issue_analysis_text
            assert bug_location_text
            assert repository_code == ORIGINAL_CODE
            assert proposed_patch.strip()

            return {
                "verdict": challenger_verdict,
                "findings": [],
                "potential_regressions": [],
                "required_corrections": [],
                "explanation": "Mock review completed."
            }

        # Patch creation and restoration
        if (
            module_name == "core.patch_manager"
            and function_name == "create_patch"
        ):
            state["patch_calls"] += 1

            modified_code = args[2]

            if modified_code == ORIGINAL_CODE:
                state["restore_calls"] += 1

            return {
                "success": True,
                "file_path": "calculator.py",
                "original_code": state["current_code"],
                "modified_code": modified_code
            }

        # Patch application
        if (
            module_name == "core.patch_manager"
            and function_name == "apply_patch"
        ):
            patch = args[1]
            state["current_code"] = patch["modified_code"]

            return {
                "success": True,
                "message": "Patch applied."
            }

        # Actual file diff
        if (
            module_name == "core.patch_manager"
            and function_name == "get_file_diff"
        ):
            return {
                "success": True,
                "diff": "--- original\n+++ modified\n"
            }

        # Regression testing
        if module_name == "verification.regression":
            index = state["regression_calls"]
            state["regression_calls"] += 1

            outcome = regression_outcomes[index]

            return {
                "test_status": outcome,
                "passed": outcome == "passed",
                "logs": "Mock regression result: {}".format(outcome)
            }

        # Final verification
        if module_name == "verification.verifier":
            return {
                "passed": True,
                "message": "Verification completed."
            }

        # Fix Passport
        if module_name == "reports.fix_passport":
            return {
                "success": True,
                "report_path": "mock-fix-passport.pdf"
            }

        raise AssertionError(
            "Unexpected module call: {}.{}".format(
                module_name,
                function_name
            )
        )

    monkeypatch.setattr(
        workflow,
        "_call",
        fake_call
    )

    return task_id, state


def test_complete_workflow_reaches_approval(
    monkeypatch,
    tmp_path
):
    task_id, state = prepare_workflow(
        monkeypatch,
        tmp_path,
        regression_outcomes=["passed"]
    )

    workflow._run_workflow(task_id)

    task = workflow._load_task(task_id)

    assert task["status"] == "awaiting_approval"
    assert task["stage"] == "finished"
    assert task["progress_percent"] == 100

    assert task["language"] == "python"
    assert task["verification"]["passed"] is True

    assert task["challenger_review"]["verdict"] == "APPROVE"

    assert state["repair_calls"] == 1
    assert state["challenge_calls"] == 1
    assert state["regression_calls"] == 1

    assert task["repair_retries_used"] == 0
    assert len(task["repair_history"]) == 1

    results = workflow.get_task_results(task_id)

    assert results["status"] == "awaiting_approval"
    assert results["bug_file"] == "calculator.py"
    assert results["modified_code"] == FIXED_CODE


def test_workflow_retries_after_regression_failure(
    monkeypatch,
    tmp_path
):
    task_id, state = prepare_workflow(
        monkeypatch,
        tmp_path,
        regression_outcomes=["failed", "passed"]
    )

    workflow._run_workflow(task_id)

    task = workflow._load_task(task_id)

    assert task["status"] == "awaiting_approval"

    assert state["repair_calls"] == 2
    assert state["challenge_calls"] == 2
    assert state["regression_calls"] == 2

    assert state["restore_calls"] == 1

    assert task["repair_attempt"] == 2
    assert task["repair_retries_used"] == 1

    assert len(task["repair_history"]) == 2

    assert task["repair_history"][0]["test_status"] == "failed"
    assert task["repair_history"][1]["test_status"] == "passed"

    assert state["repair_feedback"][0] is None

    assert state["repair_feedback"][1]["test_status"] == "failed"


def test_workflow_stops_after_two_failed_retries(
    monkeypatch,
    tmp_path
):
    task_id, state = prepare_workflow(
        monkeypatch,
        tmp_path,
        regression_outcomes=[
            "failed",
            "failed",
            "failed"
        ]
    )

    workflow._run_workflow(task_id)

    task = workflow._load_task(task_id)

    assert task["status"] == "failed"
    assert task["error"]["code"] == "REGRESSION_TEST_FAILED"
    assert task["stage"] == "regression_testing"

    assert state["repair_calls"] == 3
    assert state["challenge_calls"] == 3
    assert state["regression_calls"] == 3

    assert state["restore_calls"] == 2

    assert task["repair_attempt"] == 3
    assert task["repair_retries_used"] == 2

    assert len(task["repair_history"]) == 3


def test_workflow_stops_when_challenger_rejects_fix(
    monkeypatch,
    tmp_path
):
    task_id, state = prepare_workflow(
        monkeypatch,
        tmp_path,
        regression_outcomes=["passed"],
        challenger_verdict="REJECT"
    )

    workflow._run_workflow(task_id)

    task = workflow._load_task(task_id)

    assert task["status"] == "failed"
    assert task["error"]["code"] == "PATCH_INVALID"
    assert task["stage"] == "challenging_fix"

    assert state["repair_calls"] == 1
    assert state["challenge_calls"] == 1

    # A rejected patch must never be applied.
    assert state["patch_calls"] == 0
    assert state["regression_calls"] == 0

def test_workflow_stops_when_baseline_tests_pass(
    monkeypatch,
    tmp_path
):
    task_id, state = prepare_workflow(
        monkeypatch,
        tmp_path,
        regression_outcomes=["passed"]
    )

    # Simulate baseline tests passing.
    def fake_call(module_name, function_name, *args, **kwargs):
        if module_name == "github.issue_reader":
            return {
                "success": True,
                "number": 1,
                "title": "Handle division by zero",
                "body": "The divide function should handle zero."
            }

        if (
            module_name == "github.repo_manager"
            and function_name == "clone_repository"
        ):
            return {
                "success": True,
                "repository_path": str(tmp_path / "repository"),
                "default_branch": "main",
                "commit_sha": "original-commit"
            }

        if (
            module_name == "github.repo_manager"
            and function_name == "create_working_copy"
        ):
            return {
                "success": True,
                "workspace_path": str(tmp_path / "workspace")
            }

        if module_name == "languages.language_detector":
            return "python"

        if module_name == "sandbox.docker_manager":
            return True

        if module_name == "verification.baseline":
            return {
                "test_status": "passed",
                "passed": True,
                "logs": "All baseline tests passed."
            }

        raise AssertionError(
            "Workflow continued unexpectedly: {}.{}".format(
                module_name,
                function_name
            )
        )

    monkeypatch.setattr(workflow, "_call", fake_call)

    workflow._run_workflow(task_id)

    task = workflow._load_task(task_id)

    assert task["status"] == "failed"
    assert task["error"]["code"] == "BASELINE_TEST_FAILED"
    assert task["stage"] == "baseline_testing"

    assert task["baseline_result"]["test_status"] == "passed"

    # No AI agent or patch operation should execute.
    assert state["repair_calls"] == 0
    assert state["challenge_calls"] == 0
    assert state["patch_calls"] == 0
    assert state["regression_calls"] == 0

