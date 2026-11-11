import streamlit as st

from core.workflow import get_task_progress


STAGE_LABELS = {
    "queued": "Task queued",
    "reading_issue": "Reading GitHub issue",
    "cloning_repository": "Cloning repository",
    "detecting_language": "Detecting programming language",
    "baseline_testing": "Running baseline tests",
    "analyzing_issue": "Analyzing issue",
    "locating_bug": "Locating bug",
    "generating_fix": "Generating proposed fix",
    "challenging_fix": "Reviewing proposed fix",
    "applying_patch": "Applying patch",
    "regression_testing": "Running regression tests",
    "preparing_report": "Preparing Fix Passport",
    "creating_pull_request": "Creating Pull Request",
    "finished": "Workflow finished"
}


def render_progress(task_id: str) -> dict | None:
    """
    Fetch and display the latest debugging progress.

    Args:
        task_id: Unique debugging task ID.

    Returns:
        dict: Backend progress response.
        None: If progress cannot be retrieved.
    """

    st.subheader("Debugging Progress")

    if st.button("Refresh Progress", key="refresh_progress"):
        st.rerun()

    try:
        progress = get_task_progress(task_id)

        if not isinstance(progress, dict):
            st.error("Invalid progress response from backend.")
            return None

        error = progress.get("error")

        if error:
            st.error(
                error.get("message", "Unable to retrieve task progress.")
            )
            return progress

        status = progress.get("status", "pending")
        stage = progress.get("stage", "queued")
        message = progress.get(
            "message",
            "Waiting for backend update."
        )

        st.write(f"**Task ID:** `{progress.get('task_id', task_id)}`")
        st.write(f"**Status:** `{status}`")
        st.write(
            f"**Current Stage:** "
            f"{STAGE_LABELS.get(stage, stage)}"
        )

        progress_percent = progress.get("progress_percent")

        if progress_percent is not None:
            if (
                not isinstance(progress_percent, int)
                or isinstance(progress_percent, bool)
                or not 0 <= progress_percent <= 100
            ):
                st.warning("Backend returned an invalid progress percentage.")
            else:
                st.progress(progress_percent / 100)
                st.caption(f"{progress_percent}% completed")

        st.info(message)

        if progress.get("updated_at"):
            st.caption(
                f"Last updated: {progress['updated_at']}"
            )

        if status == "failed":
            st.error("The debugging task failed.")

        elif status == "awaiting_approval":
            st.success("The proposed fix is waiting for your approval.")

        elif status == "completed":
            st.success("The debugging task is completed.")

        return progress

    except Exception as exc:
        st.error(f"Could not retrieve debugging progress: {exc}")
        return None