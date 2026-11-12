"""Direct UI integration tests: no real workflow, AI, Docker, or GitHub calls."""

import ast
from concurrent.futures import Future
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, MagicMock, create_autospec, patch

from ui import backend


class WorkflowContract:
    def start_debugging(self, repo_url: str, issue_number: int) -> dict:
        pass

    def get_task_progress(self, task_id: str) -> dict:
        pass

    def get_task_results(self, task_id: str) -> dict:
        pass

    def approve_fix(self, task_id: str, create_pull_request: bool = True) -> dict:
        pass

    def reject_fix(self, task_id: str, reason: str = None) -> dict:
        pass


class DeferredExecutor:
    """Capture approval work without creating a thread or executing a backend."""
    def __init__(self):
        self.calls = []

    def submit(self, function, *args, **kwargs):
        future = Future()
        self.calls.append((future, function, args, kwargs))
        return future

    def finish(self):
        future, function, args, kwargs = self.calls[-1]
        try:
            future.set_result(function(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)


class _FrontendCase(unittest.TestCase):
    def setUp(self):
        self.workflow = create_autospec(WorkflowContract, instance=True)
        self.workflow.start_debugging.return_value = {
            "task_id": "task-123456789abc", "status": "pending", "stage": "queued", "message": "Accepted",
        }
        self.workflow.get_task_results.return_value = {
            "task_id": "task-123456789abc", "status": "awaiting_approval",
            "language": "python", "verification": {"baseline": None, "regression": None},
        }
        self.workflow.approve_fix.return_value = {
            "task_id": "task-123456789abc", "status": "approved", "pull_request_url": "https://github.com/example/project/pull/1",
        }
        self.workflow.reject_fix.return_value = {"task_id": "task-123456789abc", "status": "rejected"}
        self.executor = DeferredExecutor()
        workflow_patch = patch.object(backend, "_workflow", return_value=self.workflow)
        workflow_patch.start()
        self.addCleanup(workflow_patch.stop)
        executor_patch = patch.object(backend, "_DECISIONS", self.executor)
        executor_patch.start()
        self.addCleanup(executor_patch.stop)
        self.state = {}


class FrontendBackendTests(_FrontendCase):
    def test_local_health_checks_entry_points_without_executing_them(self):
        self.assertEqual(backend.local_status(), {"status": "ok", "docker_available": None})
        self.assertEqual(self.workflow.mock_calls, [])
        with patch.object(backend, "_workflow", side_effect=backend.BackendError("unavailable")):
            self.assertIsNone(backend.local_status())

    def test_contract_matches_real_workflow_signatures_without_importing_it(self):
        source = Path(__file__).resolve().parents[1] / "core/workflow.py"
        functions = {node.name: node for node in ast.parse(source.read_text(encoding="utf-8-sig")).body if isinstance(node, ast.FunctionDef)}
        expected = {
            "start_debugging": ["repo_url", "issue_number"],
            "get_task_progress": ["task_id"], "get_task_results": ["task_id"],
            "approve_fix": ["task_id", "create_pull_request"], "reject_fix": ["task_id", "reason"],
        }
        for name, arguments in expected.items():
            with self.subTest(function=name):
                self.assertEqual([arg.arg for arg in functions[name].args.args], arguments)

    def test_submission_is_direct_and_repeated_reruns_reuse_task(self):
        first = backend.submit_task(self.state, "https://github.com/example/project", 3)
        second = backend.submit_task(self.state, "https://github.com/example/project.git/", 3)
        self.assertIs(first, second)
        self.workflow.start_debugging.assert_called_once_with(repo_url="https://github.com/example/project", issue_number=3)

    def test_explicit_new_run_reset_does_not_happen_on_navigation(self):
        backend.submit_task(self.state, "https://github.com/example/project", 3)
        backend.reset_submission(self.state, "https://github.com/example/project", 3)
        backend.submit_task(self.state, "https://github.com/example/project", 3)
        self.assertEqual(self.workflow.start_debugging.call_count, 2)

    def test_unknown_submission_outcome_is_not_retried_or_leaked(self):
        self.workflow.start_debugging.side_effect = RuntimeError("secret-token-never-display")
        for _ in range(2):
            with self.assertRaises(backend.BackendError) as raised:
                backend.submit_task(self.state, "https://github.com/example/project", 3)
            self.assertNotIn("secret-token", str(raised.exception))
        self.assertEqual(self.workflow.start_debugging.call_count, 1)

    def test_structured_error_and_invalid_responses(self):
        response = {"status": "failed", "error": {"code": "INVALID_INPUT", "message": "Invalid issue", "details": "private"}}
        self.workflow.start_debugging.return_value = response
        self.assertIs(backend.submit_task(self.state, "https://github.com/example/project", 0), response)
        self.assertEqual(backend.error_message(response), "Invalid issue")
        for malformed in (None, [], {}, {"status": "pending"}):
            with self.subTest(response=malformed):
                self.workflow.start_debugging.return_value = malformed
                with self.assertRaises(backend.BackendError):
                    backend.submit_task({}, "https://github.com/example/project", 1)

    def test_polling_uses_actual_calls_and_is_not_cached(self):
        self.workflow.get_task_progress.side_effect = [{"status": "running", "stage": "baseline_testing"}, {"status": "awaiting_approval", "stage": "finished"}]
        self.assertEqual(backend.get_task_progress("task-123456789abc")["status"], "running")
        self.assertEqual(backend.get_task_progress("task-123456789abc")["status"], "awaiting_approval")
        backend.get_task_results("task-123456789abc")
        self.workflow.get_task_results.assert_called_once_with(task_id="task-123456789abc")

    def test_approval_is_asynchronous_and_not_duplicated_on_reruns(self):
        response = backend.submit_decision(self.state, "task-123456789abc", "approve", create_pull_request=False)
        self.assertEqual(response["status"], "running")
        self.workflow.approve_fix.assert_not_called()
        backend.submit_decision(self.state, "task-123456789abc", "approve")
        backend.submit_decision(self.state, "task-123456789abc", "reject", reason="late click")
        self.assertEqual(len(self.executor.calls), 1)
        self.executor.finish()
        self.workflow.approve_fix.assert_called_once_with(task_id="task-123456789abc", create_pull_request=False)
        self.assertEqual(backend.decision_status(self.state, "task-123456789abc")["status"], "approved")
        backend.submit_decision(self.state, "task-123456789abc", "approve")
        self.assertEqual(len(self.executor.calls), 1)

    def test_rejection_uses_reason_and_never_creates_pr(self):
        backend.submit_decision(self.state, "task-123456789abc", "reject", reason="Needs coverage")
        self.executor.finish()
        self.workflow.reject_fix.assert_called_once_with(task_id="task-123456789abc", reason="Needs coverage")
        self.workflow.approve_fix.assert_not_called()
        self.assertEqual(backend.decision_status(self.state, "task-123456789abc")["status"], "rejected")

    def test_stale_or_failed_backend_state_blocks_decisions(self):
        for status in ("pending", "running", "failed", "approved", "rejected"):
            with self.subTest(status=status):
                self.workflow.get_task_results.return_value = {"status": status}
                self.assertEqual(backend.submit_decision({}, "task-123456789abc", "approve")["status"], status)
        self.assertEqual(len(self.executor.calls), 0)

    def test_decision_errors_are_visible_without_automatic_retry(self):
        self.workflow.approve_fix.side_effect = RuntimeError("sensitive-token")
        backend.submit_decision(self.state, "task-123456789abc", "approve")
        self.executor.finish()
        response = backend.decision_status(self.state, "task-123456789abc")
        self.assertEqual(response["status"], "failed")
        self.assertNotIn("sensitive-token", str(response))
        backend.submit_decision(self.state, "task-123456789abc", "approve")
        self.assertEqual(len(self.executor.calls), 1)

    def test_reentrant_rerun_during_preflight_cannot_enqueue_twice(self):
        def read(task_id):
            pending = backend.submit_decision(self.state, task_id, "approve")
            self.assertEqual(pending["status"], "running")
            return {"status": "awaiting_approval"}
        self.workflow.get_task_results.side_effect = read
        backend.submit_decision(self.state, "task-123456789abc", "approve")
        self.assertEqual(len(self.executor.calls), 1)


class FrontendRenderingTests(_FrontendCase):
    def setUp(self):
        super().setUp()
        self.st = types.ModuleType("streamlit")
        for name in (
            "header", "subheader", "title", "caption", "markdown", "write", "code", "error", "warning",
            "info", "success", "divider", "metric", "progress", "set_page_config", "container", "form", "expander",
        ):
            setattr(self.st, name, MagicMock())
        self.st.sidebar = MagicMock()
        self.st.sidebar.radio.return_value = "Dashboard"
        self.st.session_state = self.state
        self.st.columns = Mock(side_effect=lambda count, **kwargs: [MagicMock() for _ in range(count if isinstance(count, int) else len(count))])
        self.st.text_input = Mock(side_effect=lambda label, **kwargs: "https://github.com/example/project" if "URL" in label else "3")
        self.st.text_area = Mock(return_value="Needs tests")
        self.st.form_submit_button = Mock(return_value=False)
        self.st.button = Mock(return_value=False)
        self.st.checkbox = Mock(return_value=True)
        self.st.rerun = Mock()
        modules = patch.dict(sys.modules, {"streamlit": self.st})
        modules.start()
        self.addCleanup(modules.stop)
        self.modules = {}
        for name in ("issue_form", "progress", "results", "approval", "dashboard"):
            module = importlib.import_module("ui." + name)
            self.modules[name] = module
            streamlit_patch = patch.object(module, "st", self.st)
            streamlit_patch.start()
            self.addCleanup(streamlit_patch.stop)

    def test_submission_render_preserves_task_session_state(self):
        self.st.form_submit_button.return_value = True
        self.modules["issue_form"].show_issue_form()
        self.state["task_status"] = "running"
        self.state["task_stage"] = "baseline_testing"
        self.modules["issue_form"].show_issue_form()
        self.assertEqual(self.state["task_id"], "task-123456789abc")
        self.assertEqual(self.state["task_stage"], "baseline_testing")
        self.assertEqual(self.state["task_status"], "running")
        self.assertEqual(self.state["issue_number"], 3)
        self.workflow.start_debugging.assert_called_once()

    def test_bad_inputs_do_not_start_workflow(self):
        self.st.form_submit_button.return_value = True
        self.st.text_input.side_effect = ["invalid", "3"]
        self.modules["issue_form"].show_issue_form()
        self.workflow.start_debugging.assert_not_called()
        self.st.error.assert_called()

    def test_progress_and_results_display_actual_backend_fields(self):
        self.workflow.get_task_progress.return_value = {"task_id": "task-123456789abc", "status": "running", "stage": "baseline_testing", "progress_percent": 25, "message": "Testing", "error": None}
        self.modules["progress"].show_progress("task-123456789abc")
        self.assertEqual(self.state["task_message"], "Testing")
        self.st.progress.assert_called_once_with(25)
        result = self.modules["results"].render_results("task-123456789abc")
        self.assertEqual(result["status"], "awaiting_approval")
        self.st.markdown.assert_any_call("### Verification Results")

    def test_approval_render_preserves_pr_option_and_blocks_stale_reruns(self):
        self.st.button.side_effect = lambda label, **kwargs: label == "Approve Fix"
        self.st.checkbox.return_value = False
        first = self.modules["approval"].show_approval("task-123456789abc")
        self.assertEqual(first["status"], "running")
        self.modules["approval"].show_approval("task-123456789abc")
        self.assertEqual(len(self.executor.calls), 1)
        self.executor.finish()
        result = self.modules["approval"].show_approval("task-123456789abc")
        self.assertEqual(result["status"], "approved")
        self.workflow.approve_fix.assert_called_once_with(task_id="task-123456789abc", create_pull_request=False)

    def test_rejection_render_strips_reason(self):
        self.st.form_submit_button.return_value = True
        self.st.text_area.return_value = "  Needs tests  "
        self.modules["approval"].show_approval("task-123456789abc")
        self.executor.finish()
        self.workflow.reject_fix.assert_called_once_with(task_id="task-123456789abc", reason="Needs tests")

    def test_backend_errors_are_displayed_without_enabling_approval(self):
        self.workflow.get_task_results.return_value = {"status": "failed", "error": {"message": "Task unavailable", "details": "secret"}}
        self.modules["approval"].show_approval("task-123456789abc")
        self.st.error.assert_called_with("Task unavailable")
        self.assertEqual(len(self.executor.calls), 0)

    def test_results_keep_code_diff_verification_review_and_pr_link(self):
        self.workflow.get_task_results.return_value = {
            "task_id": "task-123456789abc", "status": "approved", "language": "python",
            "original_code": "before", "modified_code": "after", "diff": "-before\n+after",
            "bug_file": "main.py", "bug_location": "main", "bug_explanation": "Off by one",
            "challenger_review": {"verdict": "APPROVE", "explanation": "Review explanation"},
            "verification": {"baseline": {"test_status": "failed", "passed": False, "exit_code": 1, "logs": "baseline"}, "regression": {"test_status": "passed", "passed": True, "exit_code": 0, "logs": "regression"}},
            "pull_request_url": "https://github.com/example/project/pull/1",
        }
        result = self.modules["results"].render_results("task-123456789abc")
        self.assertEqual(result["status"], "approved")
        self.st.code.assert_any_call("before", language="python")
        self.st.code.assert_any_call("after", language="python")
        self.st.code.assert_any_call("-before\n+after", language="diff")
        self.st.write.assert_any_call("**Explanation:** Review explanation")
        self.st.markdown.assert_any_call("[Open Pull Request](https://github.com/example/project/pull/1)")

    def test_both_challenger_panels_render_actual_backend_fields(self):
        for panel in ("results", "approval"):
            for verdict in ("APPROVE", "REJECT", "NEEDS_REVISION"):
                with self.subTest(panel=panel, verdict=verdict):
                    self.st.write.reset_mock()
                    self.workflow.get_task_results.return_value = {
                        "task_id": "task-123456789abc", "status": "awaiting_approval",
                        "challenger_review": {
                            "verdict": verdict, "explanation": "Review reasoning",
                            "findings": ["Finding one", "Finding two"],
                            "potential_regressions": ["Boundary case risk"],
                            "required_corrections": ["Add boundary check"],
                        },
                    }
                    render = self.modules[panel].render_results if panel == "results" else self.modules[panel].show_approval
                    result = render("task-123456789abc")
                    self.assertEqual(result["status"], "awaiting_approval")
                    if panel == "results":
                        self.st.write.assert_any_call(f"**Verdict:** {verdict}")
                        self.st.write.assert_any_call("**Explanation:** Review reasoning")
                    else:
                        self.st.write.assert_any_call("**Verdict:**", verdict)
                        self.st.write.assert_any_call("**Explanation:**", "Review reasoning")
                    for title in ("Findings", "Potential Regressions", "Required Corrections"):
                        self.st.write.assert_any_call(f"**{title}:**")
                    for entry in ("Finding one", "Finding two", "Boundary case risk", "Add boundary check"):
                        self.st.write.assert_any_call(f"- {entry}")
                    displayed = str(self.st.write.call_args_list)
                    self.assertNotIn("Risk Level", displayed)
                    self.assertNotIn("Challenger Approved", displayed)
                    self.assertNotIn("Approved by Challenger", displayed)
                    self.assertEqual(len(self.executor.calls), 0)

    def test_challenger_empty_optional_fields_and_absent_review_are_safe(self):
        for panel in ("results", "approval"):
            for review in (None, {}, {"verdict": "APPROVE", "findings": [], "potential_regressions": None, "required_corrections": []}):
                with self.subTest(panel=panel, review=review):
                    self.st.caption.reset_mock()
                    self.workflow.get_task_results.return_value = {"status": "awaiting_approval", "challenger_review": review}
                    render = self.modules[panel].render_results if panel == "results" else self.modules[panel].show_approval
                    render("task-123456789abc")
                    if review:
                        for field in ("findings", "potential regressions", "required corrections"):
                            self.st.caption.assert_any_call(f"No {field} reported.")
                    else:
                        self.st.caption.assert_any_call("Challenger review is not available.")
                    self.assertEqual(len(self.executor.calls), 0)

    def test_all_navigation_pages_render_without_http_or_side_effects(self):
        for page in ("Dashboard", "Report Issue", "Progress", "Results", "Approval"):
            with self.subTest(page=page):
                self.st.sidebar.radio.return_value = page
                self.modules["dashboard"].render_dashboard()
        self.workflow.start_debugging.assert_not_called()
        self.workflow.approve_fix.assert_not_called()
        self.workflow.reject_fix.assert_not_called()


if __name__ == "__main__":
    unittest.main()
