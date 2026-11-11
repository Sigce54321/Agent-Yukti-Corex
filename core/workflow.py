
import os
import re
import json
import uuid
import logging
import importlib
import subprocess
import threading

from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

WORKSPACES_DIR = Path(
    os.getenv(
        "YUKTICOREX_WORKSPACES_DIR",
        str(BASE_DIR / "workspaces")
    )
).resolve()

TASK_RECORDS_DIR = WORKSPACES_DIR / "_task_records"

WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
TASK_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("yukticorex.workflow")

TASKS = {}
TASK_LOCK = threading.RLock()

EXECUTOR = ThreadPoolExecutor(max_workers=3)


# ============================================================
# WORKFLOW STAGES AND PROGRESS
# ============================================================

PROGRESS = {
    "queued": 0,
    "reading_issue": 5,
    "cloning_repository": 10,
    "detecting_language": 15,
    "baseline_testing": 25,
    "analyzing_issue": 35,
    "locating_bug": 45,
    "generating_fix": 55,
    "challenging_fix": 65,
    "applying_patch": 70,
    "regression_testing": 80,
    "preparing_report": 90,
    "creating_pull_request": 95,
    "finished": 100
}


# ============================================================
# CUSTOM WORKFLOW ERROR
# ============================================================

class WorkflowError(Exception):

    def __init__(
        self,
        code,
        message,
        details=None,
        stage=None
    ):
        super().__init__(message)

        self.code = code
        self.message = message
        self.details = details or ""
        self.stage = stage or "finished"


# ============================================================
# GENERAL HELPERS
# ============================================================

def _now():
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value):
    """
    Convert values into JSON-compatible data.
    """

    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _error_response(
    task_id,
    code,
    message,
    details="",
    stage="finished"
):
    return {
        "status": "failed",
        "task_id": task_id,
        "error": {
            "code": code,
            "message": message,
            "details": str(details),
            "stage": stage
        }
    }


def _validate_repo_url(repo_url):
    if not isinstance(repo_url, str):
        raise WorkflowError(
            "INVALID_INPUT",
            "Repository URL must be a string.",
            "Invalid repository URL type.",
            "queued"
        )

    repo_url = repo_url.strip()

    pattern = (
        r"^https://github\.com/"
        r"[A-Za-z0-9_.-]+/"
        r"[A-Za-z0-9_.-]+"
        r"(?:\.git)?/?$"
    )

    if not re.match(pattern, repo_url):
        raise WorkflowError(
            "INVALID_REPOSITORY_URL",
            "Please provide a valid public GitHub repository URL.",
            "Expected format: https://github.com/owner/repository",
            "queued"
        )

    return repo_url.rstrip("/")


def _validate_issue_number(issue_number):
    if (
        isinstance(issue_number, bool)
        or not isinstance(issue_number, int)
        or issue_number <= 0
    ):
        raise WorkflowError(
            "INVALID_INPUT",
            "Issue number must be a positive integer.",
            "Invalid GitHub issue number.",
            "queued"
        )

    return issue_number


# ============================================================
# TASK STORAGE
# ============================================================

def _task_file(task_id):
    return TASK_RECORDS_DIR / "{}.json".format(task_id)


def _save_task(task):
    """
    Save task information using atomic JSON replacement.
    """

    task_id = task["task_id"]
    file_path = _task_file(task_id)

    temporary_path = file_path.with_suffix(".tmp")

    with TASK_LOCK:
        task["updated_at"] = _now()

        with open(
            temporary_path,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                _json_safe(task),
                file,
                indent=4
            )

        os.replace(temporary_path, file_path)

        TASKS[task_id] = task


def _load_task(task_id):
    """
    Load task from memory or persistent JSON storage.
    """

    if (
        not isinstance(task_id, str)
        or not re.fullmatch(r"task-[a-f0-9]{12}", task_id)
    ):
        return None

    with TASK_LOCK:

        if task_id in TASKS:
            return TASKS[task_id]

        file_path = _task_file(task_id)

        if not file_path.exists():
            return None

        try:
            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as file:
                task = json.load(file)

            # A background thread cannot resume after restart.
            if task.get("status") == "running":

                task["status"] = "failed"
                task["message"] = (
                    "Task was interrupted by an application restart."
                )

                task["error"] = {
                    "code": "INTERNAL_ERROR",
                    "message": "Workflow execution was interrupted.",
                    "details": (
                        "The application restarted before the task finished."
                    ),
                    "stage": task.get("stage", "finished")
                }

                task["stage"] = "finished"
                task["progress_percent"] = 100

                _save_task(task)

            TASKS[task_id] = task
            return task

        except (OSError, json.JSONDecodeError):
            logger.exception("Could not load task record.")
            return None


def _update_task(task_id, **updates):
    with TASK_LOCK:

        task = _load_task(task_id)

        if task is None:
            return None

        task.update(updates)
        task["updated_at"] = _now()

        _save_task(task)

        return task


def _set_stage(task_id, stage, message, **updates):
    if stage not in PROGRESS:
        raise WorkflowError(
            "INTERNAL_ERROR",
            "Invalid workflow stage.",
            "Unknown stage: {}".format(stage),
            stage
        )

    updates.update({
        "status": "running",
        "stage": stage,
        "progress_percent": PROGRESS[stage],
        "message": message
    })

    return _update_task(task_id, **updates)


# ============================================================
# MODULE CALL HELPER
# ============================================================

def _call(module_name, function_name, *args, **kwargs):
    """
    Import and execute another project module.
    """

    try:
        module = importlib.import_module(module_name)
        function = getattr(module, function_name)

        return function(*args, **kwargs)

    except WorkflowError:
        raise

    except Exception as exc:
        logger.exception(
            "Module call failed: %s.%s",
            module_name,
            function_name
        )

        raise WorkflowError(
            "INTERNAL_ERROR",
            "A workflow module could not be executed.",
            "{}.{}: {}".format(
                module_name,
                function_name,
                exc
            )
        )


def _require_dict(result, module_name):
    if not isinstance(result, dict):
        raise WorkflowError(
            "AI_INVALID_RESPONSE",
            "A module returned an invalid response.",
            "{} must return a dictionary.".format(module_name)
        )

    if result.get("success") is False:
        error = result.get("error") or {}

        raise WorkflowError(
            error.get("code", "INTERNAL_ERROR"),
            error.get("message", "Module execution failed."),
            error.get("details", str(result))
        )

    if result.get("status") == "failed":
        error = result.get("error") or {}

        raise WorkflowError(
            error.get("code", "INTERNAL_ERROR"),
            error.get("message", "Module execution failed."),
            error.get("details", str(result))
        )

    return result


# ============================================================
# REPOSITORY SUMMARY
# ============================================================

def _repository_summary(repository_path):
    """
    Build a limited text summary for the Issue Analyzer.
    """

    root = Path(repository_path).resolve()

    ignored_directories = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        ".next",
        "target"
    }

    allowed_extensions = {
        ".py",
        ".java",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".html",
        ".css"
    }

    files = []
    total_characters = 0
    maximum_characters = 30000

    try:
        for current_root, directories, filenames in os.walk(root):

            directories[:] = [
                directory
                for directory in directories
                if directory not in ignored_directories
            ]

            for filename in filenames:

                file_path = Path(current_root) / filename

                if file_path.suffix.lower() not in allowed_extensions:
                    continue

                try:
                    relative_path = file_path.relative_to(root)

                    content = file_path.read_text(
                        encoding="utf-8",
                        errors="replace"
                    )

                    remaining = maximum_characters - total_characters

                    if remaining <= 0:
                        break

                    content = content[:remaining]

                    files.append({
                        "file_path": str(relative_path).replace("\\", "/"),
                        "content": content
                    })

                    total_characters += len(content)

                except (OSError, ValueError):
                    continue

            if total_characters >= maximum_characters:
                break

    except OSError as exc:
        raise WorkflowError(
            "INTERNAL_ERROR",
            "Could not read repository files.",
            str(exc),
            "analyzing_issue"
        )

    return {
        "repository_path": str(root),
        "files": files,
        "file_count": len(files)
    }


# ============================================================
# WORKFLOW RESULT VALIDATION
# ============================================================

def _validate_issue(issue):
    if not isinstance(issue, dict):
        raise WorkflowError(
            "AI_INVALID_RESPONSE",
            "GitHub issue data is invalid.",
            "Issue reader must return a dictionary.",
            "reading_issue"
        )

    if not issue.get("title"):
        raise WorkflowError(
            "ISSUE_NOT_FOUND",
            "GitHub issue title was not found.",
            "The issue reader returned no title.",
            "reading_issue"
        )

    if issue.get("body") is None:
        issue["body"] = ""

    return issue


def _validate_language(language):
    allowed_languages = {
        "python",
        "javascript",
        "java",
        "html",
        "css"
    }

    if not isinstance(language, str):
        language = "unknown"

    language = language.strip().lower()

    if language not in allowed_languages:
        raise WorkflowError(
            "LANGUAGE_NOT_SUPPORTED",
            "The repository language is not supported.",
            "Detected language: {}".format(language),
            "detecting_language"
        )

    return language


def _validate_test_result(result, stage):
    result = _require_dict(result, "verification module")

    allowed_statuses = {
        "passed",
        "failed",
        "error",
        "not_run"
    }

    test_status = result.get("test_status")

    if test_status not in allowed_statuses:
        raise WorkflowError(
            "AI_INVALID_RESPONSE",
            "Test module returned an invalid test status.",
            "Received test_status: {}".format(test_status),
            stage
        )

    if not isinstance(result.get("passed"), bool):
        raise WorkflowError(
            "AI_INVALID_RESPONSE",
            "Test module returned an invalid passed value.",
            "The passed field must be Boolean.",
            stage
        )

    return result


def _validate_bug_location(bug_location):
    if not isinstance(bug_location, dict):
        raise WorkflowError(
            "AI_INVALID_RESPONSE",
            "Bug Locator returned an invalid response.",
            "Expected a dictionary.",
            "locating_bug"
        )

    if bug_location.get("found") is not True:
        raise WorkflowError(
            "BUG_NOT_FOUND",
            "The Bug Locator could not identify the issue.",
            bug_location.get("reason", "No matching bug was found."),
            "locating_bug"
        )

    required_fields = [
        "file_path",
        "function_name",
        "original_code"
    ]

    for field in required_fields:
        if not bug_location.get(field):
            raise WorkflowError(
                "AI_INVALID_RESPONSE",
                "Bug Locator response is incomplete.",
                "Missing field: {}".format(field),
                "locating_bug"
            )

    return bug_location


def _validate_proposed_fix(proposed_fix, bug_location):
    if not isinstance(proposed_fix, dict):
        raise WorkflowError(
            "AI_INVALID_RESPONSE",
            "Repair Agent returned an invalid response.",
            "Expected a dictionary.",
            "generating_fix"
        )

    required_fields = [
        "file_path",
        "original_code",
        "modified_code"
    ]

    for field in required_fields:
        if not isinstance(proposed_fix.get(field), str):
            raise WorkflowError(
                "AI_INVALID_RESPONSE",
                "Repair Agent response is incomplete.",
                "Missing or invalid field: {}".format(field),
                "generating_fix"
            )

    if not proposed_fix["modified_code"].strip():
        raise WorkflowError(
            "PATCH_INVALID",
            "Repair Agent generated an empty modification.",
            "Modified code cannot be empty.",
            "generating_fix"
        )

    if proposed_fix["file_path"] != bug_location["file_path"]:
        raise WorkflowError(
            "PATCH_INVALID",
            "Repair Agent selected a different file.",
            "The proposed file does not match the Bug Locator result.",
            "generating_fix"
        )

    if proposed_fix["original_code"] != bug_location["original_code"]:
        raise WorkflowError(
            "PATCH_INVALID",
            "Original code does not match the identified bug.",
            "The Repair Agent and Bug Locator returned different original code.",
            "generating_fix"
        )

    return proposed_fix


# ============================================================
# START DEBUGGING
# ============================================================

def start_debugging(repo_url: str, issue_number: int) -> dict:
    """
    Create a debugging task and execute it in the background.
    """

    try:
        repo_url = _validate_repo_url(repo_url)
        issue_number = _validate_issue_number(issue_number)

        task_id = "task-{}".format(uuid.uuid4().hex[:12])

        task = {
            "task_id": task_id,
            "repo_url": repo_url,
            "issue_number": issue_number,
            "status": "pending",
            "stage": "queued",
            "progress_percent": 0,
            "message": "Debugging task accepted.",
            "created_at": _now(),
            "updated_at": _now(),
            "error": None
        }

        _save_task(task)

        EXECUTOR.submit(
            _run_workflow,
            task_id
        )

        return {
            "task_id": task_id,
            "status": "pending",
            "stage": "queued",
            "message": "Debugging task accepted."
        }

    except WorkflowError as exc:
        return _error_response(
            None,
            exc.code,
            exc.message,
            exc.details,
            exc.stage
        )

    except Exception as exc:
        logger.exception("Could not start debugging task.")

        return _error_response(
            None,
            "INTERNAL_ERROR",
            "Could not start debugging task.",
            str(exc),
            "queued"
        )


# ============================================================
# MAIN BACKGROUND WORKFLOW
# ============================================================

def _run_workflow(task_id):
    """
    Coordinates GitHub, AI agents, Docker, verification,
    patch management and report generation.
    """

    try:
        task = _load_task(task_id)

        if task is None:
            raise WorkflowError(
                "INTERNAL_ERROR",
                "Task record was not found.",
                task_id,
                "queued"
            )

        repo_url = task["repo_url"]
        issue_number = task["issue_number"]

        # ----------------------------------------------------
        # 1. READ GITHUB ISSUE
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "reading_issue",
            "Reading GitHub issue."
        )

        issue = _call(
            "github.issue_reader",
            "read_github_issue",
            repo_url,
            issue_number
        )

        issue = _require_dict(issue, "GitHub Issue Reader")
        issue = _validate_issue(issue)

        _update_task(
            task_id,
            issue=issue,
            issue_title=issue.get("title"),
            issue_description=issue.get("body", "")
        )

        # ----------------------------------------------------
        # 2. CLONE REPOSITORY
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "cloning_repository",
            "Cloning GitHub repository."
        )

        clone_result = _call(
            "github.repo_manager",
            "clone_repository",
            repo_url,
            task_id
        )

        clone_result = _require_dict(
            clone_result,
            "Repository Manager"
        )

        repository_path = clone_result.get("repository_path")
        default_branch = clone_result.get("default_branch")

        if not repository_path or not default_branch:
            raise WorkflowError(
                "REPOSITORY_CLONE_FAILED",
                "Repository clone information is incomplete.",
                "Expected repository_path and default_branch.",
                "cloning_repository"
            )

        repository_path = str(Path(repository_path).resolve())

        if not Path(repository_path).is_dir():
            raise WorkflowError(
                "REPOSITORY_CLONE_FAILED",
                "Cloned repository directory does not exist.",
                repository_path,
                "cloning_repository"
            )

        _update_task(
            task_id,
            repository_path=repository_path,
            default_branch=default_branch,
            commit_sha=clone_result.get("commit_sha")
        )

        # ----------------------------------------------------
        # 3. CREATE SEPARATE WORKING COPY
        # ----------------------------------------------------

        working_result = _call(
            "github.repo_manager",
            "create_working_copy",
            repository_path,
            task_id
        )

        working_result = _require_dict(
            working_result,
            "Working Copy Manager"
        )

        workspace_path = working_result.get("workspace_path")

        if not workspace_path:
            raise WorkflowError(
                "INTERNAL_ERROR",
                "Working copy path was not returned.",
                str(working_result),
                "cloning_repository"
            )

        workspace_path = str(Path(workspace_path).resolve())

        if not Path(workspace_path).is_dir():
            raise WorkflowError(
                "INTERNAL_ERROR",
                "Working copy directory does not exist.",
                workspace_path,
                "cloning_repository"
            )

        if Path(workspace_path) == Path(repository_path):
            raise WorkflowError(
                "INTERNAL_ERROR",
                "Repository and workspace paths must be different.",
                "The original repository cannot be modified.",
                "cloning_repository"
            )

        _update_task(
            task_id,
            workspace_path=workspace_path
        )

        # ----------------------------------------------------
        # 4. DETECT PROGRAMMING LANGUAGE
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "detecting_language",
            "Detecting repository programming language."
        )

        language = _call(
            "languages.language_detector",
            "detect_language",
            repository_path
        )

        language = _validate_language(language)

        _update_task(
            task_id,
            language=language
        )

        # ----------------------------------------------------
        # 5. CHECK DOCKER
        # ----------------------------------------------------

        docker_available = _call(
            "sandbox.docker_manager",
            "check_docker_connection"
        )

        if docker_available is not True:
            raise WorkflowError(
                "DOCKER_UNAVAILABLE",
                "Docker is not available.",
                "Start Docker Desktop and try again.",
                "baseline_testing"
            )

        # ----------------------------------------------------
        # 6. BASELINE TESTING
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "baseline_testing",
            "Running baseline tests in Docker."
        )

        baseline_result = _call(
            "verification.baseline",
            "run_baseline_tests",
            workspace_path,
            language
        )

        baseline_result = _validate_test_result(
            baseline_result,
            "baseline_testing"
        )

        if baseline_result["test_status"] in {"error", "not_run"}:
            raise WorkflowError(
                "BASELINE_TEST_FAILED",
                "Baseline tests could not be executed.",
                baseline_result.get("logs", ""),
                "baseline_testing"
            )

        _update_task(
            task_id,
            baseline_result=baseline_result
        )

        # ----------------------------------------------------
        # 7. PREPARE REPOSITORY SUMMARY
        # ----------------------------------------------------

        repository_summary = _repository_summary(
            repository_path
        )

        # ----------------------------------------------------
        # 8. ISSUE ANALYZER
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "analyzing_issue",
            "Issue Analyzer is analyzing the GitHub issue."
        )

        issue_analysis = _call(
            "agents.issue_analyzer",
            "analyze_issue_for_backend",
            issue,
            repository_summary
        )

        issue_analysis = _require_dict(
            issue_analysis,
            "Issue Analyzer"
        )

        if not issue_analysis.get("problem_summary"):
            raise WorkflowError(
                "AI_INVALID_RESPONSE",
                "Issue Analyzer returned incomplete information.",
                "Missing problem_summary.",
                "analyzing_issue"
            )

        _update_task(
            task_id,
            issue_analysis=issue_analysis
        )

        # ----------------------------------------------------
        # 9. BUG LOCATOR
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "locating_bug",
            "Bug Locator is identifying the faulty code."
        )

        bug_location = _call(
            "agents.bug_locator",
            "locate_bug_for_backend",
            issue_analysis,
            _repository_summary(repository_path),
            language
        )

        bug_location = _validate_bug_location(
            bug_location
        )

        _update_task(
            task_id,
            bug_location=bug_location
        )

        # ----------------------------------------------------
        # 10. REPAIR AGENT
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "generating_fix",
            "Repair Agent is generating a proposed fix."
        )

        proposed_fix = _call(
    "agents.repair_agent",
    "propose_fix_for_backend",
    bug_location,
    issue_analysis,
    _repository_summary(workspace_path)
        )

        proposed_fix = _validate_proposed_fix(
            proposed_fix,
            bug_location
        )

        _update_task(
            task_id,
            proposed_fix=proposed_fix
        )

        # ----------------------------------------------------
        # 11. FIX CHALLENGER
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "challenging_fix",
            "Fix Challenger is reviewing the proposed fix."
        )

        challenger_review = _call(
            "agents.fix_challenger",
            "challenge_fix_for_backend",
            issue_analysis,
            bug_location,
            proposed_fix
        )

        challenger_review = _require_dict(
            challenger_review,
            "Fix Challenger"
        )

        allowed_risks = {
            "low",
            "medium",
            "high"
        }

        if (
            challenger_review.get("approved") is not True
            or challenger_review.get("risk_level") not in allowed_risks
        ):
            raise WorkflowError(
                "PATCH_INVALID",
                "Fix Challenger did not approve the proposed fix.",
                str(challenger_review),
                "challenging_fix"
            )

        if challenger_review.get("risk_level") == "high":
            raise WorkflowError(
                "PATCH_INVALID",
                "The proposed fix has a high risk level.",
                challenger_review.get("summary", ""),
                "challenging_fix"
            )

        _update_task(
            task_id,
            challenger_review=challenger_review
        )

        # ----------------------------------------------------
        # 12. CREATE PATCH
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "applying_patch",
            "Validating the proposed code patch."
        )

        patch = _call(
            "core.patch_manager",
            "create_patch",
            workspace_path,
            proposed_fix["file_path"],
            proposed_fix["modified_code"]
        )

        patch = _require_dict(
            patch,
            "Patch Manager"
        )

        if not patch.get("success"):
            raise WorkflowError(
                "PATCH_INVALID",
                "Patch Manager could not create the patch.",
                str(patch.get("error")),
                "applying_patch"
            )

        if patch.get("original_code") != proposed_fix["original_code"]:
            raise WorkflowError(
                "PATCH_INVALID",
                "The original file changed before patch creation.",
                "The proposed fix does not match the current file.",
                "applying_patch"
            )

        if patch.get("file_path") != proposed_fix["file_path"]:
            raise WorkflowError(
                "PATCH_INVALID",
                "Patch file path does not match the proposed fix.",
                str(patch.get("file_path")),
                "applying_patch"
            )

        # ----------------------------------------------------
        # 13. APPLY PATCH
        # ----------------------------------------------------

        apply_result = _call(
            "core.patch_manager",
            "apply_patch",
            workspace_path,
            patch
        )

        apply_result = _require_dict(
            apply_result,
            "Patch Manager"
        )

        if not apply_result.get("success"):
            raise WorkflowError(
                "PATCH_APPLY_FAILED",
                "The proposed patch could not be applied.",
                str(apply_result.get("error")),
                "applying_patch"
            )

        # Get actual difference after applying the patch.
        diff_result = _call(
            "core.patch_manager",
            "get_file_diff",
            workspace_path,
            proposed_fix["file_path"]
        )

        diff_result = _require_dict(
            diff_result,
            "Patch Manager"
        )

        actual_diff = diff_result.get("diff", "")

        proposed_fix["diff"] = actual_diff

        _update_task(
            task_id,
            patch=patch,
            apply_result=apply_result,
            diff=actual_diff,
            proposed_fix=proposed_fix
        )

        # ----------------------------------------------------
        # 14. REGRESSION TESTING
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "regression_testing",
            "Running regression tests in Docker."
        )

        regression_result = _call(
            "verification.regression",
            "run_regression_tests",
            workspace_path,
            language
        )

        regression_result = _validate_test_result(
            regression_result,
            "regression_testing"
        )

        _update_task(
            task_id,
            regression_result=regression_result
        )

        # ----------------------------------------------------
        # 15. VERIFY FIX
        # ----------------------------------------------------

        verification = _call(
            "verification.verifier",
            "verify_fix",
            baseline_result,
            regression_result
        )

        verification = _require_dict(
            verification,
            "Fix Verifier"
        )

        verification["baseline"] = baseline_result
        verification["regression"] = regression_result

        if (
            verification.get("passed") is not True
            or regression_result.get("passed") is not True
            or regression_result.get("test_status") != "passed"
        ):
            raise WorkflowError(
                "REGRESSION_TEST_FAILED",
                "The proposed fix did not pass verification.",
                regression_result.get("logs", ""),
                "regression_testing"
            )

        _update_task(
            task_id,
            verification=verification
        )

        # ----------------------------------------------------
        # 16. GENERATE FIX PASSPORT
        # ----------------------------------------------------

        _set_stage(
            task_id,
            "preparing_report",
            "Generating the Fix Passport report."
        )

        report_result = _call(
            "reports.fix_passport",
            "generate_fix_passport",
            task_id=task_id,
            issue=issue,
            bug_location=bug_location,
            proposed_fix=proposed_fix,
            verification=verification,
            challenger_review=challenger_review
        )

        report_result = _require_dict(
            report_result,
            "Fix Passport Generator"
        )

        if not report_result.get("success"):
            raise WorkflowError(
                "INTERNAL_ERROR",
                "Fix Passport generation failed.",
                str(report_result),
                "preparing_report"
            )

        # ----------------------------------------------------
        # 17. WAIT FOR USER APPROVAL
        # ----------------------------------------------------

        _update_task(
            task_id,
            status="awaiting_approval",
            stage="finished",
            progress_percent=100,
            message="Fix verified. Waiting for your approval.",
            report_result=report_result,
            pull_request_url=None,
            error=None
        )

    except WorkflowError as exc:

        logger.error(
            "Workflow failed at %s: %s",
            exc.stage,
            exc.message
        )

        _update_task(
            task_id,
            status="failed",
            stage=exc.stage,
            progress_percent=PROGRESS.get(exc.stage, 100),
            message=exc.message,
            error={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "stage": exc.stage
            }
        )

    except Exception as exc:

        logger.exception("Unexpected workflow failure.")

        _update_task(
            task_id,
            status="failed",
            stage="finished",
            progress_percent=100,
            message="An unexpected workflow error occurred.",
            error={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected workflow error occurred.",
                "details": str(exc),
                "stage": "finished"
            }
        )


# ============================================================
# GET TASK PROGRESS
# ============================================================

def get_task_progress(task_id: str) -> dict:
    task = _load_task(task_id)

    if task is None:
        return _error_response(
            task_id,
            "INVALID_INPUT",
            "Task was not found.",
            "Invalid task ID."
        )

    return {
        "task_id": task_id,
        "status": task.get("status", "pending"),
        "stage": task.get("stage", "queued"),
        "progress_percent": int(
            task.get(
                "progress_percent",
                PROGRESS.get(task.get("stage"), 0)
            )
        ),
        "message": task.get("message", ""),
        "updated_at": task.get("updated_at"),
        "error": task.get("error")
    }


# ============================================================
# GET TASK RESULTS
# ============================================================

def get_task_results(task_id: str) -> dict:
    task = _load_task(task_id)

    if task is None:
        return _error_response(
            task_id,
            "INVALID_INPUT",
            "Task was not found.",
            "Invalid task ID."
        )

    if task.get("status") == "failed":
        return {
            "task_id": task_id,
            "status": "failed",
            "message": task.get("message"),
            "error": task.get("error")
        }

    if task.get("status") != "awaiting_approval" and task.get("status") != "approved":
        return {
            "task_id": task_id,
            "status": task.get("status"),
            "message": task.get("message", "Results are not ready.")
        }

    issue = task.get("issue") or {}
    bug_location = task.get("bug_location") or {}
    proposed_fix = task.get("proposed_fix") or {}
    verification = task.get("verification") or {}

    return {
        "task_id": task_id,
        "status": task.get("status"),
        "language": task.get("language"),
        "bug_file": bug_location.get("file_path"),
        "bug_location": bug_location.get("function_name"),
        "bug_explanation": bug_location.get("reason"),
        "original_code": proposed_fix.get("original_code"),
        "modified_code": proposed_fix.get("modified_code"),
        "diff": task.get("diff", ""),
        "challenger_review": task.get("challenger_review"),
        "verification": {
            "baseline": verification.get("baseline"),
            "regression": verification.get("regression")
        },
        "pull_request_url": task.get("pull_request_url")
    }


# ============================================================
# PREPARE GIT BRANCH AFTER APPROVAL
# ============================================================

def _run_git_command(workspace_path, command):
    """
    Run Git commands without using shell=True.
    """

    result = subprocess.run(
        ["git"] + command,
        cwd=workspace_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False
    )

    if result.returncode != 0:
        raise WorkflowError(
            "PULL_REQUEST_FAILED",
            "Git operation failed.",
            result.stderr or result.stdout,
            "creating_pull_request"
        )

    return result.stdout.strip()


def _prepare_branch_for_pr(task):
    """
    Create a dedicated fix branch, commit only the fixed file,
    and push it to GitHub.
    """

    workspace_path = task.get("workspace_path")
    task_id = task["task_id"]
    file_path = task.get("bug_location", {}).get("file_path")
    default_branch = task.get("default_branch")

    if not workspace_path or not Path(workspace_path).is_dir():
        raise WorkflowError(
            "PULL_REQUEST_FAILED",
            "Working copy is unavailable.",
            str(workspace_path),
            "creating_pull_request"
        )

    if not file_path or not default_branch:
        raise WorkflowError(
            "PULL_REQUEST_FAILED",
            "Required Git information is missing.",
            "Expected file_path and default_branch.",
            "creating_pull_request"
        )

    # Confirm this is a Git working copy.
    _run_git_command(
        workspace_path,
        ["rev-parse", "--is-inside-work-tree"]
    )

    branch_name = "yukticorex/fix-{}".format(task_id)

    # Create a separate branch from the current workspace commit.
    _run_git_command(
        workspace_path,
        ["switch", "-c", branch_name]
    )

    # Stage only the repaired source file.
    _run_git_command(
        workspace_path,
        ["add", "--", file_path]
    )

    staged_files = _run_git_command(
        workspace_path,
        ["diff", "--cached", "--name-only"]
    )

    staged_list = [
        item.strip().replace("\\", "/")
        for item in staged_files.splitlines()
        if item.strip()
    ]

    if file_path.replace("\\", "/") not in staged_list:
        raise WorkflowError(
            "PULL_REQUEST_FAILED",
            "The repaired file was not staged.",
            staged_files,
            "creating_pull_request"
        )

    # Commit the repaired file.
    _run_git_command(
        workspace_path,
        [
            "commit",
            "-m",
            "Fix: {}".format(task.get("issue_title", "GitHub issue"))
        ]
    )

    # Push the dedicated branch.
    _run_git_command(
        workspace_path,
        [
            "push",
            "-u",
            "origin",
            branch_name
        ]
    )

    return branch_name, default_branch


# ============================================================
# APPROVE FIX AND CREATE PULL REQUEST
# ============================================================

def approve_fix(
    task_id: str,
    create_pull_request: bool = True
) -> dict:

    task = _load_task(task_id)

    if task is None:
        return _error_response(
            task_id,
            "INVALID_INPUT",
            "Task was not found.",
            "Invalid task ID."
        )

    if task.get("status") != "awaiting_approval":
        return _error_response(
            task_id,
            "APPROVAL_REQUIRED",
            "Task is not waiting for approval.",
            "Approval is allowed only for awaiting_approval tasks."
        )

    if not isinstance(create_pull_request, bool):
        return _error_response(
            task_id,
            "INVALID_INPUT",
            "create_pull_request must be Boolean.",
            "Expected true or false."
        )

    # Approval without creating a PR.
    if not create_pull_request:

        _update_task(
            task_id,
            status="approved",
            message="Fix approved. Pull Request was not requested."
        )

        return {
            "task_id": task_id,
            "status": "approved",
            "message": "Fix approved.",
            "pull_request_url": None
        }

    try:

        _set_stage(
            task_id,
            "creating_pull_request",
            "Preparing Git branch and creating Pull Request."
        )

        task = _load_task(task_id)

        source_branch, target_branch = _prepare_branch_for_pr(
            task
        )

        issue_title = task.get("issue_title") or "Bug fix"

        issue_url = (task.get("issue") or {}).get(
            "issue_url",
            ""
        )

        verification = task.get("verification") or {}

        body = (
            "## YuktiC-oreX Automated Fix\n\n"
            "This Pull Request contains a proposed fix "
            "generated and verified by YuktiC-oreX.\n\n"
            "### GitHub Issue\n"
            "{}\n\n"
            "### Detected Language\n"
            "{}\n\n"
            "### Verification\n"
            "- Baseline test status: {}\n"
            "- Regression test status: {}\n"
            "- Regression tests passed: {}\n\n"
            "### Bug Summary\n"
            "{}\n\n"
            "The fix was approved by the user. "
            "This Pull Request has not been merged automatically."
        ).format(
            issue_url or "Issue #{}".format(task["issue_number"]),
            task.get("language", "unknown"),
            (verification.get("baseline") or {}).get("test_status"),
            (verification.get("regression") or {}).get("test_status"),
            (verification.get("regression") or {}).get("passed"),
            (task.get("bug_location") or {}).get("reason", "")
        )

        pr_result = _call(
            "github.pull_request",
            "create_pull_request",
            task["repo_url"],
            source_branch,
            target_branch,
            "Fix: {}".format(issue_title),
            body
        )

        pr_result = _require_dict(
            pr_result,
            "GitHub Pull Request"
        )

        if pr_result.get("created") is not True:
            raise WorkflowError(
                "PULL_REQUEST_FAILED",
                "GitHub Pull Request could not be created.",
                str(pr_result),
                "creating_pull_request"
            )

        pull_request_url = pr_result.get("pull_request_url")

        if not pull_request_url:
            raise WorkflowError(
                "PULL_REQUEST_FAILED",
                "Pull Request URL was not returned.",
                str(pr_result),
                "creating_pull_request"
            )

        _update_task(
            task_id,
            status="approved",
            stage="finished",
            progress_percent=100,
            message="Fix approved and Pull Request created.",
            source_branch=source_branch,
            target_branch=target_branch,
            pull_request_url=pull_request_url,
            pull_request_number=pr_result.get("pull_request_number"),
            error=None
        )

        return {
            "task_id": task_id,
            "status": "approved",
            "message": "Fix approved.",
            "pull_request_url": pull_request_url
        }

    except WorkflowError as exc:

        _update_task(
            task_id,
            status="failed",
            stage=exc.stage,
            message=exc.message,
            error={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "stage": exc.stage
            }
        )

        return _error_response(
            task_id,
            exc.code,
            exc.message,
            exc.details,
            exc.stage
        )

    except Exception as exc:

        logger.exception("Pull Request creation failed.")

        _update_task(
            task_id,
            status="failed",
            stage="creating_pull_request",
            message="Pull Request creation failed.",
            error={
                "code": "PULL_REQUEST_FAILED",
                "message": "Pull Request creation failed.",
                "details": str(exc),
                "stage": "creating_pull_request"
            }
        )

        return _error_response(
            task_id,
            "PULL_REQUEST_FAILED",
            "Pull Request creation failed.",
            str(exc),
            "creating_pull_request"
        )


# ============================================================
# REJECT PROPOSED FIX
# ============================================================

def reject_fix(
    task_id: str,
    reason: str = None
) -> dict:

    task = _load_task(task_id)

    if task is None:
        return _error_response(
            task_id,
            "INVALID_INPUT",
            "Task was not found.",
            "Invalid task ID."
        )

    if task.get("status") != "awaiting_approval":
        return _error_response(
            task_id,
            "APPROVAL_REQUIRED",
            "Task is not waiting for approval.",
            "Only awaiting_approval tasks can be rejected."
        )

    if reason is not None and not isinstance(reason, str):
        return _error_response(
            task_id,
            "INVALID_INPUT",
            "Rejection reason must be a string.",
            "Invalid reason value."
        )

    _update_task(
        task_id,
        status="rejected",
        stage="finished",
        progress_percent=100,
        message="Proposed fix rejected.",
        rejection_reason=reason,
        error=None
    )

    return {
        "task_id": task_id,
        "status": "rejected",
        "message": "Proposed fix rejected."
    }
