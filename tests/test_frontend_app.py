"""Exercise real Streamlit forms and navigation without external side effects."""
from contextlib import ExitStack
import importlib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from ui import backend


@pytest.fixture
def workspace():
    workflow = Mock()
    workflow.get_task_progress.return_value = {
        "task_id": "task-ui", "status": "awaiting_approval", "stage": "finished",
        "progress_percent": 100, "message": "Ready for human review",
    }
    workflow.start_debugging.return_value = {
        "task_id": "task-ui", "status": "pending", "stage": "queued", "message": "Accepted",
    }
    workflow.get_task_results.return_value = {
        "task_id": "task-ui", "status": "awaiting_approval", "language": "python",
        "bug_file": "module.py", "bug_location": "divide", "bug_explanation": "Boundary error",
        "original_code": "before", "modified_code": "after", "diff": "-before\n+after",
        "challenger_review": {"verdict": "NEEDS_REVISION", "explanation": "Boundary needs coverage",
                              "findings": ["Missing edge test"], "potential_regressions": ["Zero input"],
                              "required_corrections": ["Add coverage"]},
        "verification": {"baseline": {"test_status": "failed", "passed": False, "exit_code": 1},
                         "regression": {"test_status": "passed", "passed": True, "exit_code": 0, "logs": "Test evidence"}},
    }
    with ExitStack() as stack:
        stack.enter_context(patch.object(backend, "_workflow", return_value=workflow))
        for name in ("dashboard", "issue_form", "progress", "results", "approval"):
            stack.enter_context(patch.object(importlib.import_module("ui." + name), "st", st))
        yield AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=10), workflow


def test_real_forms_submission_navigation_and_evidence(workspace):
    app, workflow = workspace
    app.run()
    assert not app.exception
    app.text_input[0].input("https://github.com/example/project")
    app.text_input[1].input("7")
    next(b for b in app.button if b.label == "Start Debugging").click().run()
    assert not app.exception
    assert app.session_state["task_id"] == "task-ui"
    workflow.start_debugging.assert_called_once_with(repo_url="https://github.com/example/project", issue_number=7)
    next(b for b in app.button if b.label == "Start Debugging").click().run()
    workflow.start_debugging.assert_called_once()
    for page in ("Progress", "Results", "Approval", "Dashboard"):
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
        if page == "Results":
            assert any(c.value == "-before\n+after" for c in app.code)
            assert any("NEEDS_REVISION" in str(m.value) for m in app.markdown)
            assert any("Test status: passed" in m.value for m in app.success)
        if page == "Approval":
            assert app.checkbox[0].value is False
    workflow.approve_fix.assert_not_called()
    workflow.reject_fix.assert_not_called()


def test_failed_task_disables_decision_controls(workspace):
    app, workflow = workspace
    workflow.get_task_results.return_value = {"task_id": "task-ui", "status": "failed", "error": {"message": "Regression failed"}}
    app.session_state["task_id"] = "task-ui"
    app.run()
    app.sidebar.radio[0].set_value("Approval").run()
    assert not app.exception
    assert not any(b.label in ("Approve Fix", "Reject Fix") for b in app.button)
    workflow.approve_fix.assert_not_called()


def test_compact_dashboard_approval_remains_guarded_across_reruns(workspace):
    from concurrent.futures import Future
    app, workflow = workspace
    future = Future()
    executor = Mock()
    executor.submit.return_value = future
    app.session_state["task_id"] = "task-ui"
    with patch.object(backend, "_DECISIONS", executor):
        app.run()
        assert not app.exception
        assert app.checkbox[0].value is False
        next(b for b in app.button if b.label == "Approve Fix").click().run()
        assert not app.exception
        app.run()
        executor.submit.assert_called_once()
        assert executor.submit.call_args.args[1] == "approve_fix"
        assert executor.submit.call_args.kwargs["create_pull_request"] is False
        assert not any(b.label in ("Approve Fix", "Reject Fix") for b in app.button)
        future.set_result({"task_id": "task-ui", "status": "approved", "message": "Approved without PR"})
        app.run()
        assert not app.exception
        executor.submit.assert_called_once()
        assert not any(b.label in ("Approve Fix", "Reject Fix") for b in app.button)
    workflow.approve_fix.assert_not_called()


def test_reference_panels_escape_backend_content():
    from ui.visuals import row, text, patch_counts
    assert "<script>" not in row("File", "<script>alert(1)</script>")
    assert text("<b>file</b>") == "&lt;b&gt;file&lt;/b&gt;"
    assert patch_counts("--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-before\n+after") == (1, 1)
    assert patch_counts(None) is None
