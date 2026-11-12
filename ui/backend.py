"""Direct workflow access and session-local guards for Streamlit reruns."""

from concurrent.futures import ThreadPoolExecutor
import importlib
import threading


_DECISIONS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ui-approval")
_GUARD = threading.RLock()
_FUNCTIONS = (
    "start_debugging", "get_task_progress", "get_task_results", "approve_fix", "reject_fix",
)


class BackendError(RuntimeError):
    """A local workflow call could not return a usable result."""


def _workflow():
    try:
        return importlib.import_module("core.workflow")
    except Exception as exc:
        raise BackendError("The local workflow could not be loaded. Check the server logs.") from exc


def local_status():
    """Check local entry points without starting tasks or probing external services."""
    try:
        workflow = _workflow()
        if all(callable(getattr(workflow, name, None)) for name in _FUNCTIONS):
            return {"status": "ok", "docker_available": None}
    except BackendError:
        pass
    return None


def _call(name, **kwargs):
    try:
        response = getattr(_workflow(), name)(**kwargs)
    except Exception as exc:
        raise BackendError("The local workflow call failed. Check the server logs before retrying.") from exc
    if not isinstance(response, dict) or not isinstance(response.get("status"), str):
        raise BackendError("The local workflow returned an invalid response.")
    return response


def error_message(response):
    """Display public error messages, never raw exception details or credentials."""
    error = response.get("error")
    if isinstance(error, dict):
        return error.get("message") or "The workflow reported an error."
    return response.get("message") or "The workflow reported an error."


def get_task_progress(task_id):
    return _call("get_task_progress", task_id=task_id)


def get_task_results(task_id):
    return _call("get_task_results", task_id=task_id)


def _submission_key(repo_url, issue_number):
    return (repo_url.strip().rstrip("/").removesuffix(".git").lower(), issue_number)


def reset_submission(state, repo_url, issue_number):
    """Explicitly permit a new run; ordinary reruns never clear this guard."""
    state.setdefault("debug_submissions", {}).pop(_submission_key(repo_url, issue_number), None)


def submit_task(state, repo_url, issue_number):
    submissions = state.setdefault("debug_submissions", {})
    key = _submission_key(repo_url, issue_number)
    with _GUARD:
        if key in submissions:
            record = submissions[key]
            if record.get("response") is not None:
                return record["response"]
            raise BackendError("Submission is pending or its outcome is uncertain. Check the task before explicitly retrying.")
        record = {}
        submissions[key] = record  # Persist before any side effect or rerun.
    response = _call("start_debugging", repo_url=repo_url, issue_number=issue_number)
    if not response.get("error") and response.get("status") != "failed" and not response.get("task_id"):
        raise BackendError("The local workflow did not return a task ID. Check the task before retrying.")
    record["response"] = response
    return response


def decision_status(state, task_id):
    """Poll an approval future without issuing another approval or rejection."""
    record = state.get("task_decisions", {}).get(task_id)
    if record is None:
        return None
    if "response" in record:
        return record["response"]
    future = record.get("future")
    if future is None or not future.done():
        return {
            "task_id": task_id, "status": "running",
            "message": "Your decision is being processed. Refresh to check its outcome.",
        }
    try:
        record["response"] = future.result()
    except Exception:
        record["response"] = {
            "task_id": task_id, "status": "failed",
            "error": {"message": "The decision outcome could not be confirmed. Check the task and GitHub before retrying."},
        }
    return record["response"]


def submit_decision(state, task_id, action, *, create_pull_request=True, reason=None):
    """Allow exactly one decision per task in this session, including uncertain outcomes."""
    decisions = state.setdefault("task_decisions", {})
    if action not in ("approve", "reject"):
        raise BackendError("Unknown approval action.")
    with _GUARD:
        if task_id in decisions:
            return decision_status(state, task_id)
        record = {"action": action}
        decisions[task_id] = record
    # Reserve the guard before this read, so concurrent reruns cannot both
    # observe awaiting_approval and enqueue duplicate side effects.
    try:
        current = get_task_results(task_id)
    except BackendError:
        record["response"] = {
            "task_id": task_id, "status": "failed",
            "error": {"message": "The current task state could not be confirmed. No decision was submitted."},
        }
        raise
    if current.get("error") or current.get("status") != "awaiting_approval":
        record["response"] = current
        return current
    kwargs = {"task_id": task_id}
    if action == "approve":
        kwargs["create_pull_request"] = create_pull_request
        name = "approve_fix"
    else:
        kwargs["reason"] = reason
        name = "reject_fix"
    try:
        record["future"] = _DECISIONS.submit(_call, name, **kwargs)
    except Exception as exc:
        record["response"] = {
            "task_id": task_id, "status": "failed",
            "error": {"message": "The decision could not be scheduled. Check the task before retrying."},
        }
        raise BackendError(record["response"]["error"]["message"]) from exc
    return decision_status(state, task_id)
