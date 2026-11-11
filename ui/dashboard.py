
import requests
import streamlit as st

from ui.issue_form import show_issue_form
from ui.progress import show_progress
from ui.results import render_results
from ui.approval import show_approval


# --------------------------------------------------
# BACKEND CONFIGURATION
# --------------------------------------------------

API_BASE_URL = "http://127.0.0.1:8000"


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

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


# --------------------------------------------------
# BACKEND HEALTH CHECK
# --------------------------------------------------

def check_backend():

    try:
        response = requests.get(
            f"{API_BASE_URL}/api/health",
            timeout=3
        )

        if response.status_code == 200:
            data = response.json()
            return data if data.get("status") == "ok" else None

        return None

    except requests.RequestException:
        return None

    except ValueError:
        return None


# --------------------------------------------------
# DASHBOARD METRICS
# --------------------------------------------------

def display_metrics():

    task_id = st.session_state.get("task_id")
    status = st.session_state.get("task_status", "pending")

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
            st.session_state.get(
                "task_stage", "queued"
            ).replace("_", " ").title()
            if task_id else "Not Started"
        )


# --------------------------------------------------
# WORKFLOW OVERVIEW
# --------------------------------------------------

def display_workflow():

    st.subheader("Autonomous Debugging Workflow")

    stages = [
        ("01", "Issue Submission", "Submit a GitHub repository and issue number."),
        ("02", "Issue Analysis", "Analyze the reported problem."),
        ("03", "Bug Detection", "Locate the affected file and function."),
        ("04", "Fix Generation", "Generate a proposed code correction."),
        ("05", "Fix Verification", "Run baseline and regression tests."),
        ("06", "Approval", "Review and approve or reject the proposed fix."),
        ("07", "Pull Request", "Create a GitHub Pull Request after approval.")
    ]

    for number, title, description in stages:

        with st.container(border=True):

            col1, col2 = st.columns([1, 9])

            with col1:
                st.markdown(f"### {number}")

            with col2:
                st.markdown(f"**{title}**")
                st.caption(description)


# --------------------------------------------------
# CURRENT TASK DETAILS
# --------------------------------------------------

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
                "repo_url", "Not available"
            )
        )

    with col2:
        st.write("**GitHub Issue Number**")
        st.write(
            st.session_state.get(
                "issue_number", "Not available"
            )
        )

    st.write(
        "**Latest Backend Message:**",
        st.session_state.get(
            "task_message", "No message available."
        )
    )


# --------------------------------------------------
# MAIN DASHBOARD
# --------------------------------------------------

def render_dashboard():

    initialize_session()

    # Header
    st.title("🛠️ YuktiC-oreX")

    st.markdown(
        "### AI-Powered Autonomous Debugging Platform"
    )

    st.caption(
        "Analyze GitHub issues, identify bugs, "
        "generate fixes, verify changes and request approval."
    )

    st.divider()

    # Sidebar navigation
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

    # Backend connection
    st.sidebar.divider()
    st.sidebar.subheader("System Status")

    health = check_backend()

    if health:

        st.sidebar.success("Backend Connected")

        docker_status = health.get("docker_available")

        if docker_status is True:
            st.sidebar.success("Docker Available")
        elif docker_status is False:
            st.sidebar.warning("Docker Unavailable")
        else:
            st.sidebar.caption("Docker status unavailable")

    else:
        st.sidebar.error("Backend Disconnected")
        st.sidebar.caption(API_BASE_URL)

    # Task information in sidebar
    st.sidebar.divider()
    st.sidebar.subheader("Active Task")

    task_id = st.session_state.get("task_id")

    if task_id:

        st.sidebar.code(task_id)

        st.sidebar.write(
            "Status:",
            st.session_state.get("task_status", "pending")
        )

    else:
        st.sidebar.caption("No active task")

    st.divider()

    # --------------------------------------------------
    # DASHBOARD HOME
    # --------------------------------------------------

    if page == "Dashboard":

        st.header("📊 Dashboard Overview")

        display_metrics()

        st.divider()

        display_current_task()

        st.divider()

        display_workflow()

    # --------------------------------------------------
    # ISSUE SUBMISSION
    # --------------------------------------------------

    elif page == "Report Issue":

        st.header("📝 Report GitHub Issue")

        show_issue_form()

    # --------------------------------------------------
    # PROGRESS
    # --------------------------------------------------

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

    # --------------------------------------------------
    # RESULTS
    # --------------------------------------------------

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

    # --------------------------------------------------
    # APPROVAL
    # --------------------------------------------------

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

    # --------------------------------------------------
    # FOOTER
    # --------------------------------------------------

    st.divider()

    st.caption(
        "YuktiC-oreX | Autonomous Bug Repair Platform"
    )

    st.caption(
        "Streamlit Frontend | Backend API Integration"
    )
