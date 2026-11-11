
import os
import requests
import streamlit as st


# --------------------------------------------------
# BACKEND CONFIGURATION
# --------------------------------------------------

API_BASE_URL = os.getenv(
    "YUKTICOREX_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")


# --------------------------------------------------
# STANDARD WORKFLOW VALUES
# --------------------------------------------------

VALID_STATUSES = {
    "pending",
    "running",
    "completed",
    "failed",
    "awaiting_approval",
    "approved",
    "rejected"
}

VALID_STAGES = [
    "queued",
    "reading_issue",
    "cloning_repository",
    "detecting_language",
    "baseline_testing",
    "analyzing_issue",
    "locating_bug",
    "generating_fix",
    "challenging_fix",
    "applying_patch",
    "regression_testing",
    "preparing_report",
    "creating_pull_request",
    "finished"
]


# --------------------------------------------------
# ERROR HANDLING
# --------------------------------------------------

def _get_error_message(response):
    """Extract a readable error message from the backend."""

    try:
        data = response.json()
        error = data.get("error")

        if isinstance(error, dict):
            return error.get(
                "message",
                "Unable to retrieve debugging progress."
            )

        if error:
            return str(error)

        return data.get(
            "message",
            response.text or "Backend request failed."
        )

    except (ValueError, AttributeError):
        return response.text or "Backend request failed."


# --------------------------------------------------
# STATUS DISPLAY
# --------------------------------------------------

def _display_status(status: str):
    """Display the official debugging task status."""

    if status == "pending":
        st.info("Task is pending and waiting to start.")

    elif status == "running":
        st.info("Debugging workflow is currently running.")

    elif status == "completed":
        st.success("Debugging task completed successfully.")

    elif status == "failed":
        st.error("Debugging task failed.")

    elif status == "awaiting_approval":
        st.warning("Proposed fix is waiting for your approval.")

    elif status == "approved":
        st.success("Proposed fix has been approved.")

    elif status == "rejected":
        st.warning("Proposed fix has been rejected.")

    else:
        st.warning(f"Unknown task status: {status}")


# --------------------------------------------------
# PROGRESS DISPLAY
# --------------------------------------------------

def _display_progress(progress_percent):
    """Display backend-reported progress percentage."""

    if (
        isinstance(progress_percent, bool)
        or not isinstance(progress_percent, int)
        or not 0 <= progress_percent <= 100
    ):
        st.warning(
            "The backend did not provide a valid "
            "progress percentage (integer between 0 and 100)."
        )
        return

    st.markdown("### Overall Progress")

    st.progress(progress_percent)

    st.metric(
        label="Progress Completed",
        value=f"{progress_percent}%"
    )


# --------------------------------------------------
# DEBUGGING PROGRESS FUNCTION
# --------------------------------------------------

def show_progress(task_id: str | None = None) -> dict | None:
    """
    Fetch and display debugging task progress.

    Args:
        task_id: Unique debugging task ID.
                 If omitted, reads from Streamlit session state.

    Backend endpoint:
        GET /api/progress/{task_id}

    Expected response:
        {
            "task_id": "task-123",
            "status": "running",
            "stage": "analyzing_issue",
            "progress_percent": 45,
            "message": "AI agents are analyzing the issue.",
            "updated_at": "2026-11-11T10:00:00Z"
        }

    Returns:
        dict: Backend progress response.
        None: If progress is unavailable.
    """

    st.subheader("Debugging Progress")

    # --------------------------------------------------
    # GET TASK ID
    # --------------------------------------------------

    if not task_id:
        task_id = st.session_state.get("task_id")

    if not task_id:
        st.info(
            "No debugging task found. "
            "Please submit a GitHub issue first."
        )
        return None

    st.write(f"**Task ID:** `{task_id}`")

    # --------------------------------------------------
    # REFRESH CONTROL
    # --------------------------------------------------

    st.caption(
        "Progress is retrieved from the backend whenever "
        "this page is loaded or refreshed."
    )

    st.button(
        "Refresh Progress",
        key=f"refresh_progress_{task_id}"
    )

    # --------------------------------------------------
    # BACKEND API REQUEST
    # --------------------------------------------------

    try:

        response = requests.get(
            f"{API_BASE_URL}/api/progress/{task_id}",
            timeout=30
        )

        try:
            data = response.json()

        except ValueError:
            st.error(
                "Backend returned an invalid JSON response."
            )
            return None

        # --------------------------------------------------
        # HANDLE API ERRORS
        # --------------------------------------------------

        if response.status_code != 200:

            st.error(_get_error_message(response))

            return data if isinstance(data, dict) else None

        if not isinstance(data, dict):
            st.error(
                "Invalid progress response received from backend."
            )
            return None

        error = data.get("error")

        if error:

            if isinstance(error, dict):
                st.error(
                    error.get(
                        "message",
                        "Unable to retrieve debugging progress."
                    )
                )
            else:
                st.error(str(error))

            return data

        # --------------------------------------------------
        # READ BACKEND RESPONSE
        # --------------------------------------------------

        returned_task_id = data.get("task_id", task_id)

        status = data.get("status")

        stage = data.get("stage")

        progress_percent = data.get("progress_percent")

        message = data.get("message")

        updated_at = data.get("updated_at")

        # --------------------------------------------------
        # UPDATE SESSION STATE
        # --------------------------------------------------

        if status:
            st.session_state["task_status"] = status

        if stage:
            st.session_state["task_stage"] = stage

        # --------------------------------------------------
        # DISPLAY TASK INFORMATION
        # --------------------------------------------------

        st.divider()

        st.markdown("### Task Information")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Task ID**")
            st.code(returned_task_id)

        with col2:
            st.write("**Task Status**")

            if isinstance(status, str):
                st.write(f"`{status}`")
            else:
                st.caption("Status not available.")

        # --------------------------------------------------
        # DISPLAY STATUS
        # --------------------------------------------------

        if isinstance(status, str):
            st.markdown("### Current Status")
            _display_status(status)

        # --------------------------------------------------
        # DISPLAY WORKFLOW STAGE
        # --------------------------------------------------

        st.markdown("### Current Workflow Stage")

        if isinstance(stage, str):

            st.write(f"**Stage:** `{stage}`")

            if stage not in VALID_STAGES:
                st.warning(
                    "The returned stage is not part of "
                    "the agreed workflow stage values."
                )

        else:
            st.caption("Workflow stage is not available.")

        # --------------------------------------------------
        # DISPLAY PROGRESS PERCENTAGE
        # --------------------------------------------------

        if progress_percent is not None:
            _display_progress(progress_percent)
        else:
            st.caption(
                "Progress percentage is not yet available."
            )

        # --------------------------------------------------
        # DISPLAY BACKEND MESSAGE
        # --------------------------------------------------

        if isinstance(message, str) and message:

            st.markdown("### Backend Message")

            st.info(message)

        # --------------------------------------------------
        # DISPLAY LAST UPDATED TIME
        # --------------------------------------------------

        if isinstance(updated_at, str) and updated_at:

            st.caption(
                f"Last Updated: {updated_at}"
            )

        return data

    # --------------------------------------------------
    # CONNECTION ERROR HANDLING
    # --------------------------------------------------

    except requests.Timeout:

        st.error(
            "Backend request timed out. "
            "Please check the backend service."
        )

        return None

    except requests.ConnectionError:

        st.error(
            "Cannot connect to the backend. "
            f"Please check {API_BASE_URL}"
        )

        return None

    except requests.RequestException as exc:

        st.error(
            f"Could not retrieve debugging progress: {exc}"
        )

        return None
