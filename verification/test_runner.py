"""Run repository tests exclusively through the Docker sandbox."""

import re
from time import perf_counter

from languages.python_adapter import PythonAdapter
from sandbox import container_runner
from sandbox.docker_manager import LANGUAGE_IMAGES


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
        if command is None and normalized_language == "python":
            command = PythonAdapter().get_test_command(workspace_path)
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
        elif exit_code == 0:
            result["test_status"] = "passed"
        elif exit_code == 5 and _is_pytest_command(command):
            result["test_status"] = "not_run"
        else:
            result["test_status"] = "failed"
        result["passed"] = result["test_status"] == "passed"
    except Exception as error:
        # Keep failures at the sandbox boundary in the same result contract.
        result["test_status"] = "error"
        result["passed"] = False
        result["logs"] = f"Unable to run tests: {error}"
    finally:
        result["duration_seconds"] = perf_counter() - started
    return result
