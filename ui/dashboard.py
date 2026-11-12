
import streamlit as st

from ui.issue_form import show_issue_form
from ui.progress import show_progress
from ui.results import render_results
from ui.approval import show_approval


# ----------------------------------------------------
# SESSION STATE
# ----------------------------------------------------

def initialize_session():
    defaults = {
        "task_id": None,
        "task_status": "pending",
        "task_stage": "queued",
        "task_message": "",
        "repo_url": "",
        "issue_number": None
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ----------------------------------------------------
# DASHBOARD METRICS
# ----------------------------------------------------

def display_metrics():

    task_id = st.session_state.get("task_id")
    status = st.session_state.get("task_status", "pending")
    stage = st.session_state.get("task_stage", "queued")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Debugging Tasks",
            "1" if task_id else "0"
        )

    with col2:
        st.metric(
            "Current Status",
            status.replace("_", " ").title()
            if task_id else "Not Started"
        )

    with col3:
        st.metric(
            "Current Stage",
            stage.replace("_", " ").title()
            if task_id else "Not Started"
        )


# ----------------------------------------------------
# WORKFLOW OVERVIEW
# ----------------------------------------------------

def display_workflow():

    st.subheader("Autonomous Debugging Workflow")

    stages = [
        ("01", "Issue Submission",
         "Submit a GitHub repository and issue number."),

        ("02", "Issue Analysis",
         "Analyze the reported problem."),

        ("03", "Bug Detection",
         "Locate the affected file and function."),

        ("04", "Fix Generation",
         "Generate a proposed code correction."),

        ("05", "Fix Verification",
         "Run baseline and regression tests."),

        ("06", "Approval",
         "Review and approve or reject the proposed fix."),

        ("07", "Pull Request",
         "Create a GitHub Pull Request after approval.")
    ]

    for number, title, description in stages:

        with st.container(border=True):

            col1, col2 = st.columns([1, 9])

            with col1:
                st.markdown(f"### {number}")

            with col2:
                st.markdown(f"**{title}**")
                st.caption(description)


# ----------------------------------------------------
# CURRENT TASK DETAILS
# ----------------------------------------------------

def display_current_task():

    task_id = st.session_state.get("task_id")

    st.subheader("Current Debugging Task")

    if not task_id:
        st.info(
            "No debugging task is currently registered. "
            "Select Report Issue to start."
        )
        return

    st.code(task_id, language="text")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Repository**")
        st.write(
            st.session_state.get(
                "repo_url",
                "Not available"
            )
        )

    with col2:
        st.write("**GitHub Issue Number**")
        st.write(
            st.session_state.get(
                "issue_number",
                "Not available"
            )
        )

    st.write(
        "**Latest Backend Message:**",
        st.session_state.get(
            "task_message",
            "No message available."
        )
    )


# ----------------------------------------------------
# SYSTEM STATUS
# ----------------------------------------------------

def display_system_status():

    st.sidebar.divider()
    st.sidebar.subheader("System Status")

    st.sidebar.success("Python Backend Mode")

    st.sidebar.caption(
        "Direct Python function execution"
    )

    st.sidebar.info(
        "No separate API server required."
    )


# ----------------------------------------------------
# ACTIVE TASK
# ----------------------------------------------------

def display_active_task():

    st.sidebar.divider()
    st.sidebar.subheader("Active Task")

    task_id = st.session_state.get("task_id")

    if task_id:

        st.sidebar.code(task_id)

        st.sidebar.write(
            "Status:",
            st.session_state.get(
                "task_status",
                "pending"
            )
        )

    else:

        st.sidebar.caption("No active task")


# ----------------------------------------------------
# MAIN DASHBOARD
# ----------------------------------------------------

def render_dashboard():

    initialize_session()

    # HEADER
    st.title("🛠️ YuktiC-oreX")

    st.markdown(
        "### AI-Powered Autonomous Debugging Platform"
    )

    st.caption(
        "Analyze GitHub issues, identify bugs, generate fixes, "
        "verify changes and request approval."
    )

    st.divider()

    # NAVIGATION
    st.sidebar.subheader("Navigation")

    page = st.sidebar.radio(
        "Select Module",
        [
            "Dashboard",
            "Report Issue",
            "Progress",
            "Results",
            "Approval"
        ],
        key="dashboard_navigation"
    )

    # SIDEBAR STATUS
    display_system_status()
    display_active_task()

    st.divider()

    # ------------------------------------------------
    # DASHBOARD PAGE
    # ------------------------------------------------

    if page == "Dashboard":

        st.header("📊 Dashboard Overview")

        display_metrics()

        st.divider()

        display_current_task()

        st.divider()

        display_workflow()

    # ------------------------------------------------
    # REPORT ISSUE PAGE
    # ------------------------------------------------

    elif page == "Report Issue":

        st.header("📝 Report GitHub Issue")

        show_issue_form()

    # ------------------------------------------------
    # PROGRESS PAGE
    # ------------------------------------------------

    elif page == "Progress":

        st.header("⏳ Debugging Progress")

        task_id = st.session_state.get("task_id")

        if task_id:

            progress_data = show_progress(task_id)

            if isinstance(progress_data, dict):

                if progress_data.get("status"):
                    st.session_state["task_status"] = (
                        progress_data["status"]
                    )

                if progress_data.get("stage"):
                    st.session_state["task_stage"] = (
                        progress_data["stage"]
                    )

                if progress_data.get("message"):
                    st.session_state["task_message"] = (
                        progress_data["message"]
                    )

        else:

            st.warning(
                "Please submit a GitHub issue before "
                "checking debugging progress."
            )

    # ------------------------------------------------
    # RESULTS PAGE
    # ------------------------------------------------

    elif page == "Results":

        st.header("📋 Debugging Results")

        task_id = st.session_state.get("task_id")

        if task_id:

            result_data = render_results(task_id)

            if isinstance(result_data, dict):

                if result_data.get("status"):
                    st.session_state["task_status"] = (
                        result_data["status"]
                    )

        else:

            st.warning(
                "No debugging task available. "
                "Submit an issue first."
            )

    # ------------------------------------------------
    # APPROVAL PAGE
    # ------------------------------------------------

    elif page == "Approval":

        st.header("✅ Fix Approval")

        task_id = st.session_state.get("task_id")

        if task_id:

            approval_data = show_approval(task_id)

            if isinstance(approval_data, dict):

                if approval_data.get("status"):
                    st.session_state["task_status"] = (
                        approval_data["status"]
                    )

        else:

            st.warning(
                "No debugging task available for approval."
            )

    # ------------------------------------------------
    # FOOTER
    # ------------------------------------------------

    st.divider()

    st.caption(
        "YuktiC-oreX | Autonomous Bug Repair Platform"
    )

    st.caption(
        "Streamlit UI | Direct Python Backend Integration"
    )
