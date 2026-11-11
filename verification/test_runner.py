"""Run repository tests exclusively through the Docker sandbox."""

import re
from time import perf_counter

from languages.python_adapter import PythonAdapter
from languages.java_adapter import JavaAdapter
from languages.javascript_adapter import JavaScriptAdapter
from languages.html_adapter import HTMLAdapter
from languages.css_adapter import CSSAdapter
from sandbox import container_runner
from sandbox.docker_manager import LANGUAGE_IMAGES


_ADAPTERS = {
    "python": PythonAdapter,
    "java": JavaAdapter,
    "javascript": JavaScriptAdapter,
    "html": HTMLAdapter,
    "css": CSSAdapter,
}


def _test_status(command: list[str], exit_code: int, logs: str) -> str:
    """Fail closed unless runner output demonstrates executed test outcomes.

    Skipped/collected tests are not executed tests. Unrecognized output cannot
    prove a pass or a reproduced bug. Custom Java main tests use explicit PASS
    lines or a thrown AssertionError as their lightweight outcome protocol.
    """
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", logs)
    text = re.sub(r"^\s*ℹ\s+", "# ", text, flags=re.MULTILINE)
    if exit_code < 0 or exit_code in (126, 127, 137, 143):
        return "error"
    if _is_pytest_command(command):
        if exit_code in (2, 3, 4):
            return "error"
        if exit_code == 5:
            return "not_run"

    # These are execution/collection failures, not assertion outcomes, even
    # when other tests completed before the failure.
    if re.search(
        r"ModuleNotFoundError|ImportError|Cannot find (?:module|package)|"
        r"ERR_MODULE_NOT_FOUND|SyntaxError|Error collecting|INTERNALERROR|"
        r"error during collection|errors during collection|"
        r"Could not resolve (?:dependencies|artifact)|"
        r"Could not find artifact|has not been downloaded|"
        r"COMPILATION ERROR|PluginResolutionException|DependencyResolutionException|"
        r"Executable doesn't exist|browserType\.launch|"
        r"Test suite failed to run|Test timeout of|"
        r"TimeoutError:\s*(?:page|frame)\.(?:goto|reload|waitForURL)|"
        r"Target page, context or browser has been closed|"
        r"net::ERR_|\b(?:ECONNREFUSED|ENOTFOUND|ENOMEM)\b|"
        r"worker process exited unexpectedly|Java heap space",
        text, re.IGNORECASE,
    ):
        return "error"

    executable = command[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    playwright_assertion = (
        executable in ("playwright", "playwright.cmd")
        and re.search(r"expect\([^\n]*\)\.(?:not\.)?to[A-Za-z]+\b", text)
    )
    # Playwright retries web assertions until their assertion timeout. A
    # TimeoutError accompanying an expect matcher is a test failure, whereas
    # launch/network failures above always take precedence, even in mixed logs.
    if "timeouterror" in text.lower() and not playwright_assertion:
        return "error"
    if executable in ("java", "java.exe") and any(arg.endswith(".java") for arg in command[1:]):
        if exit_code != 0:
            return "failed" if re.search(r'Exception in thread "[^\"]+" java\.lang\.AssertionError\b', text) else "error"
        return "passed" if re.search(r"^\s*PASS(?:\s*:|\s*$)", text, re.MULTILINE) else "not_run"

    maven = re.findall(
        r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)",
        text,
    )
    if executable in ("mvn", "mvn.cmd", "mvn.exe") and not maven:
        return "not_run" if exit_code == 0 else "error"
    if maven:
        counts = [tuple(map(int, row)) for row in maven]
        if any(errors for _, _, errors, _ in counts):
            return "error"
        passed = sum(total - failed - skipped for total, failed, _, skipped in counts)
        failed = sum(row[1] for row in counts)
    elif re.search(r"^\s*# (?:tests|pass|fail)\s+\d+", text, re.MULTILINE):
        # Node TAP/spec summaries include test-file failures for load errors.
        if re.search(r"^\s*# cancelled\s+[1-9]", text, re.MULTILINE):
            return "error"
        passed = sum(map(int, re.findall(r"^\s*# pass\s+(\d+)", text, re.MULTILINE)))
        failed = sum(map(int, re.findall(r"^\s*# fail\s+(\d+)", text, re.MULTILINE)))
        if failed and not re.search(r"ERR_ASSERTION|AssertionError", text):
            return "error"
    else:
        # Jest's Tests line excludes suite counts; pytest and Playwright use
        # direct outcome summaries. Do not interpret collected/running counts.
        jest = re.findall(r"^\s*Tests:\s*(.*)$", text, re.MULTILINE)
        known_runner = _is_pytest_command(command) or executable in ("playwright", "playwright.cmd")
        if not known_runner and not jest:
            return "not_run" if exit_code == 0 else "error"
        summary = "\n".join(jest) if jest else text
        # Keep counts on one line: a stack frame ending in :14:34 followed
        # by "Error Context" is not a summary reporting 34 errors.
        if re.search(r"\b[1-9]\d*[ \t]+(?:errors?|interrupted|timed out)\b", summary, re.IGNORECASE):
            return "error"
        passed = sum(map(int, re.findall(r"\b(\d+)\s+passed\b", summary)))
        failed = sum(map(int, re.findall(r"\b(\d+)\s+failed\b", summary)))
    if exit_code == 0:
        if failed:
            return "error"
        return "passed" if passed > 0 else "not_run"
    return "failed" if failed > 0 else "error"


def _is_pytest_command(command: list[str]) -> bool:
    """Recognize direct pytest and Python's pytest module invocation."""
    executable = command[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    if executable in {"pytest", "pytest.exe", "py.test", "py.test.exe"}:
        return True
    return bool(
        re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", executable)
        and len(command) >= 3
        and command[1:3] == ["-m", "pytest"]
    )


def run_tests(
    workspace_path: str,
    language: str,
    execution_command: list[str] | None = None,
) -> dict:
    """Return test outcomes separately from sandbox execution failures."""
    started = perf_counter()
    result = {
        "test_status": "not_run",
        "passed": False,
        "exit_code": None,
        "logs": "",
        "execution_command": [],
        "duration_seconds": 0.0,
    }
    try:
        normalized_language = language.strip().lower() if isinstance(language, str) else ""
        if normalized_language not in LANGUAGE_IMAGES:
            result["logs"] = "Unsupported language; no tests were run."
            return result

        command = execution_command
        if command is None:
            command = _ADAPTERS[normalized_language]().get_test_command(workspace_path)
        if (
            not isinstance(command, list)
            or not command
            or any(not isinstance(arg, str) or "\x00" in arg for arg in command)
            or not command[0].strip()
            or command[0].startswith("-")
        ):
            result["logs"] = "No valid test command is available. Supply a nonempty argument list."
            return result

        result["execution_command"] = command.copy()
        execution = container_runner.run_in_container(
            workspace_path, normalized_language, command.copy()
        )
        result["logs"] = execution.get("logs") or ""
        exit_code = execution.get("exit_code")
        result["exit_code"] = exit_code if type(exit_code) is int else None
        if (
            execution.get("success") is not True
            or execution.get("timed_out")
            or result["exit_code"] is None
        ):
            result["test_status"] = "error"
            if not result["logs"]:
                result["logs"] = "Sandbox timed out or could not execute tests reliably."
        else:
            result["test_status"] = _test_status(command, exit_code, result["logs"])
        result["passed"] = result["test_status"] == "passed"
    except Exception as error:
        # Keep failures at the sandbox boundary in the same result contract.
        result["test_status"] = "error"
        result["passed"] = False
        result["logs"] = f"Unable to run tests: {error}"
    finally:
        result["duration_seconds"] = perf_counter() - started
    return result
