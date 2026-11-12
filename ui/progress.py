
import streamlit as st
from ui import backend


# --------------------------------------------------
# BACKEND CONFIGURATION
# --------------------------------------------------



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

    Uses the local get_task_progress function on every page refresh.

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

        data = backend.get_task_progress(task_id)

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
        if message:
            st.session_state["task_message"] = message

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

    except backend.BackendError as exc:
        st.error(str(exc))
        return None


def render_timeline(stage=None, status=None):
    """Stage position only; the timeline never invents outcomes or timestamps."""
    from ui.visuals import title, text, badge
    groups = [
        ("Issue intake", ["queued", "reading_issue", "cloning_repository", "detecting_language"]),
        ("Baseline tests", ["baseline_testing"]),
        ("Bug location", ["analyzing_issue", "locating_bug"]),
        ("Patch & review", ["generating_fix", "challenging_fix", "applying_patch"]),
        ("Regression tests", ["regression_testing", "preparing_report"]),
        ("Human approval", ["finished", "creating_pull_request"]),
    ]
    current = next((i for i, (_, stages) in enumerate(groups) if stage in stages), None)
    label = stage.replace("_", " ").title() if isinstance(stage, str) else "Not started"
    html = '<div class="timeline-heading">' + title("Repair Progress Timeline", "branch") + badge(label) + '</div><div class="workflow-track">'
    for i, (name, _) in enumerate(groups):
        state, hint = "pending", "Pending"
        if current is not None:
            if i < current:
                state, hint = "earlier", "Earlier stage"
            elif i == current:
                state = "failed" if status == "failed" else "current"
                hint = str(status or "Current").replace("_", " ").title()
        html += f'<div class="workflow-step {state}"><div class="step-dot">{i+1}</div><b>{name}</b><small>{text(hint)}</small></div>'
    st.markdown(html + '</div>', unsafe_allow_html=True)
    st.caption("Workflow position only. Test outcomes are reported separately; no timing or completion metrics are inferred.")


def render_agents(stage=None, status=None):
    """Display actual agent names and activity derived from the workflow stage."""
    from ui.visuals import title, icon
    st.markdown(title("Agent Status", "bug"), unsafe_allow_html=True)
    agents = [("Issue Analyzer", "analyzing_issue", "flask"), ("Bug Locator", "locating_bug", "bug"), ("Fix Generator", "generating_fix", "code"), ("Fix Challenger", "challenging_fix", "shield")]
    html = '<div class="agent-grid">'
    for name, agent_stage, symbol in agents:
        activity, css = "Pending", ""
        if stage == agent_stage:
            activity = "Failed" if status == "failed" else "Active" if status == "running" else "Inactive"
            css = "active" if activity == "Active" else ""
        elif stage in VALID_STAGES and VALID_STAGES.index(stage) > VALID_STAGES.index(agent_stage):
            activity = "Earlier stage"
        html += f'<div class="agent-card {css}"><div class="agent-icon">{icon(symbol, 24)}</div><div><b>{name}</b><small><span class="activity-dot"></span>{activity}</small></div></div>'
    st.markdown(html + '</div>', unsafe_allow_html=True)
    st.caption("Stage-derived activity · individual agent telemetry unavailable")
