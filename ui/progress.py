
import streamlit as st

from core.workflow import get_task_progress


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
# STATUS DISPLAY
# --------------------------------------------------

def _display_status(status: str):

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

    if (
        isinstance(progress_percent, bool)
        or not isinstance(progress_percent, int)
        or not 0 <= progress_percent <= 100
    ):
        st.warning("Invalid progress percentage received.")
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
        "Progress is retrieved directly from the Python workflow."
    )

    refresh_clicked = st.button(
        "Refresh Progress",
        key=f"refresh_progress_{task_id}"
    )

    if refresh_clicked:
        st.rerun()

    # --------------------------------------------------
    # GET PROGRESS FROM PYTHON WORKFLOW
    # --------------------------------------------------

    try:

        data = get_task_progress(task_id)

        if not isinstance(data, dict):
            st.error("Invalid response from Python workflow.")
            return None

        # --------------------------------------------------
        # HANDLE WORKFLOW ERRORS
        # --------------------------------------------------

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
        # READ TASK INFORMATION
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

        if message is not None:
            st.session_state["task_message"] = message

        # --------------------------------------------------
        # TASK INFORMATION
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
                st.code(status)
            else:
                st.caption("Status not available.")

        # --------------------------------------------------
        # CURRENT STATUS
        # --------------------------------------------------

        if isinstance(status, str):

            st.markdown("### Current Status")

            _display_status(status)

            if status not in VALID_STATUSES:
                st.warning("Unknown workflow status received.")

        # --------------------------------------------------
        # CURRENT WORKFLOW STAGE
        # --------------------------------------------------

        st.markdown("### Current Workflow Stage")

        if isinstance(stage, str):

            st.write(f"**Stage:** `{stage}`")

            if stage not in VALID_STAGES:
                st.warning(
                    "The returned stage is not part of "
                    "the configured workflow stages."
                )

        else:
            st.caption("Workflow stage is not available.")

        # --------------------------------------------------
        # PROGRESS PERCENTAGE
        # --------------------------------------------------

        if progress_percent is not None:

            _display_progress(progress_percent)

        else:

            st.caption("Progress percentage is not available.")

        # --------------------------------------------------
        # WORKFLOW MESSAGE
        # --------------------------------------------------

        if isinstance(message, str) and message:

            st.markdown("### Workflow Message")

            st.info(message)

        # --------------------------------------------------
        # ERROR DETAILS
        # --------------------------------------------------

        if isinstance(data.get("error"), dict):

            with st.expander("Error Details"):

                st.json(data["error"])

        # --------------------------------------------------
        # LAST UPDATED
        # --------------------------------------------------

        if isinstance(updated_at, str) and updated_at:

            st.caption(f"Last Updated: {updated_at}")

        return data

    except Exception as exc:

        st.error(
            f"Could not retrieve debugging progress: {exc}"
        )

        return None
