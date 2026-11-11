"""Verification regressions using mocked Docker results, never containers."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verification import test_runner
from verification.baseline import run_baseline_tests
from verification.regression import run_regression_tests
from verification.verifier import verify_fix


class TestRunnerTests(unittest.TestCase):
    def run_result(self, command, code=0, logs="", **overrides):
        execution = dict(success=True, exit_code=code, logs=logs, timed_out=False)
        execution.update(overrides)
        with patch.object(test_runner.container_runner, "run_in_container", return_value=execution):
            return test_runner.run_tests("unused", "python", command)

    def test_zero_tests_never_pass(self):
        cases = [
            (["python", "-m", "pytest", "--pass-with-no-tests"], "no tests ran"),
            (["node", "--test"], "# tests 0\n# pass 0\n# fail 0"),
            (["npm", "test"], "Tests: 2 skipped, 2 total"),
            (["mvn", "test"], "Tests run: 0, Failures: 0, Errors: 0, Skipped: 0"),
            (["mvn", "test"], "Tests run: 2, Failures: 0, Errors: 0, Skipped: 2"),
            (["playwright", "test"], "2 skipped"),
            (["java", "Test.java"], ""),
            (["node", "-e", ""], ""),
            (["custom"], "1 passed"),
        ]
        for command, logs in cases:
            with self.subTest(command=command, logs=logs):
                result = self.run_result(command, logs=logs)
                self.assertEqual(result["test_status"], "not_run")
                self.assertFalse(result["passed"])

    def test_real_test_passes(self):
        cases = [
            (["python", "-m", "pytest", "-q"], "1 passed in 0.1s"),
            (["node", "--test"], "# tests 1\n# pass 1\n# fail 0"),
            (["node", "--test"], "ℹ tests 1\nℹ pass 1\nℹ fail 0"),
            (["npm", "test"], "Test Suites: 1 passed\nTests: 2 passed, 2 total"),
            (["mvn", "test"], "Tests run: 2, Failures: 0, Errors: 0, Skipped: 1"),
            (["playwright", "test"], "1 passed (0.5s)"),
            (["java", "HtmlContractTest.java"], "PASS: HTML contract"),
        ]
        for command, logs in cases:
            with self.subTest(command=command):
                result = self.run_result(command, logs=logs)
                self.assertEqual(result["test_status"], "passed")
                self.assertTrue(result["passed"])

    def test_assertion_failures_are_reproduction_evidence(self):
        cases = [
            (["python", "-m", "pytest"], "1 failed in 0.1s"),
            (["npm", "test"], "Tests: 1 failed, 1 total"),
            (["node", "--test"], "AssertionError [ERR_ASSERTION]\n# pass 0\n# fail 1"),
            (["mvn", "test"], "Tests run: 1, Failures: 1, Errors: 0, Skipped: 0"),
            (["playwright", "test"], "1 failed"),
            (["java", "HtmlContractTest.java"], 'Exception in thread "main" java.lang.AssertionError: bug'),
        ]
        for command, logs in cases:
            with self.subTest(command=command):
                result = self.run_result(command, 1, logs)
                self.assertEqual(result["test_status"], "failed")
                self.assertFalse(result["passed"])

    def test_infrastructure_errors_cannot_reproduce_bug(self):
        cases = [
            (["python", "-m", "pytest"], 2, "1 passed, 1 error"),
            (["python", "-m", "pytest"], 3, "internal failure"),
            (["python", "-m", "pytest"], 4, "invalid arguments"),
            (["npm", "test"], 1, "Cannot find module 'missing'\nTests: 1 failed"),
            (["npm", "test"], 1, "Test suite failed to run"),
            (["node", "--test"], 1, "SyntaxError\n# fail 1"),
            (["node", "--test"], 1, "TypeError\n# fail 1"),
            (["node", "--test"], 1, "# pass 1\n# cancelled 1"),
            (["mvn", "test"], 1, "Could not resolve dependencies"),
            (["mvn", "test"], 1, "COMPILATION ERROR"),
            (["mvn", "test"], 1, "Tests run: 1, Failures: 0, Errors: 1, Skipped: 0"),
            (["playwright", "test"], 1, "browserType.launch: missing browser\n1 failed"),
            (["playwright", "test"], 1, "Test timeout of 30000ms exceeded\n1 failed"),
            (["playwright", "test"], 1, "page.goto: net::ERR_CONNECTION_REFUSED\n1 failed"),
            (["java", "Test.java"], 1, "error: cannot find symbol"),
            (["node", "--test"], 137, "# pass 1\n# fail 1\nAssertionError"),
        ]
        for command, code, logs in cases:
            with self.subTest(command=command, logs=logs):
                result = self.run_result(command, code, logs)
                self.assertEqual(result["test_status"], "error")
                self.assertFalse(verify_fix(result, {"test_status": "passed"})["passed"])

    def test_docker_failure_and_timeout_override_passing_logs(self):
        for overrides in ({"success": False}, {"timed_out": True}):
            with self.subTest(overrides=overrides):
                result = self.run_result(["python", "-m", "pytest"], logs="1 passed", **overrides)
                self.assertEqual(result["test_status"], "error")
                self.assertFalse(result["passed"])

    def test_html_and_css_playwright_assertion_timeouts_are_failed(self):
        for language, matcher, expected, received in (
            ("html", "toHaveAttribute", "subtract", "add"),
            ("css", "toHaveCSS", "rgb(0, 128, 0)", "rgb(255, 0, 0)"),
        ):
            for error_prefix in ("Error", "TimeoutError"):
                with self.subTest(language=language, error_prefix=error_prefix):
                    logs = (
                        "Running 1 test using 1 worker\n"
                        f"{error_prefix}: expect(locator).{matcher}(expected) failed\n"
                        f"Expected: '{expected}'\nReceived: '{received}'\n"
                        "Timeout: 5000ms\n1 failed\n"
                    )
                    execution = dict(success=True, exit_code=1, logs=logs, timed_out=False)
                    with patch.object(test_runner.container_runner, "run_in_container", return_value=execution):
                        result = test_runner.run_tests("unused", language, ["playwright", "test"])
                    self.assertEqual(result["test_status"], "failed")
                    self.assertFalse(result["passed"])
                    self.assertEqual(result["logs"], logs)
                    self.assertTrue(verify_fix(result, {"test_status": "passed"})["passed"])

    def test_playwright_infrastructure_overrides_assertion_evidence(self):
        errors = (
            "TimeoutError: browserType.launch: Timeout 30000ms exceeded",
            "browserType.launch: Executable doesn't exist",
            "TimeoutError: page.goto: Timeout 30000ms exceeded",
            "page.goto: net::ERR_CONNECTION_REFUSED",
            "Target page, context or browser has been closed",
            "Cannot find module '@playwright/test'",
            "Test timeout of 30000ms exceeded",
        )
        for language in ("html", "css"):
            for error in errors:
                with self.subTest(language=language, error=error):
                    logs = "expect(locator).toHaveCSS(expected) failed\n" + error + "\n1 failed"
                    execution = dict(success=True, exit_code=1, logs=logs, timed_out=False)
                    with patch.object(test_runner.container_runner, "run_in_container", return_value=execution):
                        result = test_runner.run_tests("unused", language, ["playwright", "test"])
                    self.assertEqual(result["test_status"], "error")
                    self.assertFalse(verify_fix(result, {"test_status": "passed"})["passed"])

    def test_unattributed_timeout_remains_error(self):
        result = self.run_result(["playwright", "test"], 1, "TimeoutError: operation timed out\n1 failed")
        self.assertEqual(result["test_status"], "error")

    def test_actual_html_baseline_log_is_assertion_failure(self):
        # Embedded real Docker output; do not read ignored workspace fixtures.
        logs = '''
Running 1 test using 1 worker

[1/1] tests/html.spec.js:5:1 › Subtract option sends the correct operation
  1) tests/html.spec.js:5:1 › Subtract option sends the correct operation ──────────────────────────

    Error: expect(locator).toHaveAttribute(expected) failed

    Locator:  locator('#operation option').filter({ hasText: 'Subtract' })
    Expected: "subtract"
    Received: "add"
    Timeout:  5000ms

    Call log:
      - Expect "toHaveAttribute" locator('#operation option').filter({ hasText: 'Subtract' }) with timeout 5000ms
      - waiting for locator('#operation option').filter({ hasText: 'Subtract' })
        14 × locator resolved to <option value="add">Subtract</option>
           - unexpected value "add"


      12 |     });
      13 |
    > 14 |     await expect(subtractOption).toHaveAttribute("value", "subtract");
         |                                  ^
      15 | });
        at /workspace/tests/html.spec.js:14:34

    Error Context: ../tmp/playwright-results/tests-html-Subtract-option-sends-the-correct-operation/error-context.md


  1 failed
    tests/html.spec.js:5:1 › Subtract option sends the correct operation ───────────────────────────
'''
        for language in ("html", "css"):
            for newline in ("\n", "\r\n"):
                with self.subTest(language=language, newline=repr(newline)):
                    actual_logs = logs.replace("\n", newline)
                    execution = dict(success=True, exit_code=1, logs=actual_logs, timed_out=False)
                    with patch.object(test_runner.container_runner, "run_in_container", return_value=execution):
                        result = test_runner.run_tests("unused", language, ["playwright", "test"])
                    self.assertEqual(result["test_status"], "failed")
                    self.assertFalse(result["passed"])
                    self.assertEqual(result["logs"], actual_logs)

    def test_real_error_counts_still_override_assertion_failures(self):
        for summary in ("1 error", "2 errors", "1 interrupted", "1 timed out"):
            with self.subTest(summary=summary):
                logs = "expect(locator).toHaveAttribute(expected) failed\n1 failed\n" + summary
                result = self.run_result(["playwright", "test"], 1, logs)
                self.assertEqual(result["test_status"], "error")

    def test_pytest_no_collection_exit(self):
        result = self.run_result(["python", "-m", "pytest"], 5, "no tests ran")
        self.assertEqual(result["test_status"], "not_run")

    def test_unrecognized_nonzero_command_is_error(self):
        self.assertEqual(self.run_result(["custom"], 1)["test_status"], "error")

    def test_invalid_commands_and_unsupported_language_do_not_execute(self):
        with patch.object(test_runner.container_runner, "run_in_container") as run:
            for command in ([], "pytest", [""], [None], ["-bad"], ["bad\x00"]):
                with self.subTest(command=command):
                    self.assertEqual(test_runner.run_tests("unused", "python", command)["test_status"], "not_run")
            self.assertEqual(test_runner.run_tests("unused", "ruby", ["ruby"])["test_status"], "not_run")
            run.assert_not_called()

    def test_wrappers_select_all_five_real_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pom.xml").write_text("<project/>", encoding="utf-8")
            (root / "package.json").write_text('{"scripts":{"test":"jest"}}', encoding="utf-8")
            tests = root / "tests"
            tests.mkdir()
            (tests / "page.spec.js").write_text("const {test}=require('@playwright/test');", encoding="utf-8")
            expected = {"python": "python", "java": "mvn", "javascript": "npm", "html": "playwright", "css": "playwright"}
            summaries = {
                "python": "1 passed",
                "java": "Tests run: 1, Failures: 0, Errors: 0, Skipped: 0",
                "javascript": "Tests: 1 passed, 1 total",
                "html": "1 passed",
                "css": "1 passed",
            }
            for wrapper in (run_baseline_tests, run_regression_tests):
                for language, executable in expected.items():
                    with self.subTest(wrapper=wrapper.__name__, language=language):
                        execution = dict(success=True, timed_out=False, exit_code=0, logs=summaries[language])
                        with patch.object(test_runner.container_runner, "run_in_container", return_value=execution) as run:
                            result = wrapper(str(root), language)
                        self.assertEqual(run.call_args.args[1], language)
                        self.assertEqual(result["execution_command"][0], executable)
                        self.assertTrue(result["passed"])
                        self.assertEqual(set(result), {"test_status", "passed", "exit_code", "logs", "execution_command", "duration_seconds"})
                        self.assertGreaterEqual(result["duration_seconds"], 0)

    def test_empty_non_python_workspaces_do_not_execute(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(test_runner.container_runner, "run_in_container") as run:
                for language in ("java", "javascript", "html", "css"):
                    with self.subTest(language=language):
                        self.assertEqual(run_baseline_tests(directory, language)["test_status"], "not_run")
                run.assert_not_called()

    def test_explicit_command_bypasses_adapter(self):
        with patch.object(test_runner.PythonAdapter, "get_test_command", side_effect=AssertionError("unexpected adapter call")):
            self.assertTrue(self.run_result(["python", "-m", "pytest", "-q"], logs="1 passed")["passed"])

    def test_sandbox_exception_is_error(self):
        with patch.object(test_runner.container_runner, "run_in_container", side_effect=OSError("unavailable")):
            result = test_runner.run_tests("unused", "python")
        self.assertEqual(result["test_status"], "error")
        self.assertIn("unavailable", result["logs"])


if __name__ == "__main__":
    unittest.main()
