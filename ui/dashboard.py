import streamlit as st

from core.workflow import start_debugging

from ui.issue_form import render_issue_form
from ui.progress import render_progress
from ui.results import render_results
from ui.approval import render_approval


def _start_new_task() -> None:
    """Start a debugging task using the submitted issue details."""

    issue_data = render_issue_form()

    if issue_data is None:
        return

    try:
        with st.spinner("Submitting debugging task..."):
            response = start_debugging(
                repo_url=issue_data["repo_url"],
                issue_number=issue_data["issue_number"]
            )

        if isinstance(response, str):
            task_id = response

        elif isinstance(response, dict):
            error = response.get("error")

            if error:
                st.error(
                    error.get(
                        "message",
                        "Unable to start debugging."
                    )
                )
                return

            task_id = response.get("task_id")

        else:
            task_id = None

        if not task_id:
            st.error(
                "Backend did not return a valid task ID."
            )
            return

        st.session_state["task_id"] = task_id
        st.session_state["repo_url"] = issue_data["repo_url"]
        st.session_state["issue_number"] = issue_data["issue_number"]

        st.success(
            f"Debugging task accepted. Task ID: {task_id}"
        )

        st.rerun()

    except Exception as exc:
        st.error(f"Could not start debugging: {exc}")


def render_dashboard() -> None:
    """Render the complete YuktiC-oreX dashboard."""

    st.title("YuktiC-oreX")
    st.caption(
        "AI-Powered Autonomous Multi-Language Bug Repair "
        "and Verification Platform"
    )

    st.divider()

    # Repository and issue submission
    _start_new_task()

    task_id = st.session_state.get("task_id")

    if not task_id:
        st.info(
            "Submit a GitHub repository and issue number "
            "to start debugging."
        )
        return

    st.divider()

    # Current task
    st.markdown("## Current Debugging Task")

    st.write(f"**Task ID:** `{task_id}`")

    if st.session_state.get("repo_url"):
        st.write(
            f"**Repository:** {st.session_state['repo_url']}"
        )

    if st.session_state.get("issue_number"):
        st.write(
            f"**Issue Number:** "
            f"#{st.session_state['issue_number']}"
        )

    st.divider()

    # Progress
    progress = render_progress(task_id)

    task_status = (
        progress.get("status", "pending")
        if isinstance(progress, dict)
        else "pending"
    )

    st.divider()

    # Results
    results = render_results(task_id)

    if isinstance(results, dict):
        result_status = results.get("status")

        if result_status:
            task_status = result_status

    st.divider()

    # Approval and rejection
    render_approval(
        task_id=task_id,
        task_status=task_status
    )

    st.divider()

    if st.button(
        "Clear Current Task",
        key="clear_current_task"
    ):
        st.session_state.pop("task_id", None)
        st.session_state.pop("repo_url", None)
        st.session_state.pop("issue_number", None)

        st.rerun()