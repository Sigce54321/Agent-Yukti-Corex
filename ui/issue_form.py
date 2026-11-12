
from urllib.parse import urlparse 
import streamlit as st

from github.issue_reader import read_github_issue
from core.workflow import start_debugging


# --------------------------------------------------
# REPOSITORY URL VALIDATION
# --------------------------------------------------


from urllib.parse import urlparse


def _validate_repository_url(repo_url):

    repo_url = repo_url.strip()

    try:
        parsed = urlparse(repo_url)

        if parsed.scheme != "https":
            return False

        if parsed.netloc.lower() != "github.com":
            return False

        parts = [
            part for part in parsed.path.strip("/").split("/")
            if part
        ]

        if len(parts) != 2:
            return False

        if not parts[0] or not parts[1]:
            return False

        return True

    except Exception:
        return False


# --------------------------------------------------
# ERROR DISPLAY
# --------------------------------------------------

def _show_error(error_data):

    if isinstance(error_data, dict):

        error = error_data.get("error", {})

        if isinstance(error, dict):

            st.error(
                error.get(
                    "message",
                    "An error occurred."
                )
            )

            details = error.get("details")

            if details:
                with st.expander("Error Details"):
                    st.write(details)

            return

    st.error(str(error_data))


# --------------------------------------------------
# ISSUE SUBMISSION FORM
# --------------------------------------------------

def show_issue_form():

    st.header("GitHub Issue Submission")

    st.write(
        "Submit a GitHub repository and issue number "
        "to start autonomous debugging."
    )

    st.divider()

    # --------------------------------------------------
    # INPUT FORM
    # --------------------------------------------------

    with st.form("issue_submission_form"):

        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/owner/repository"
        )

        issue_number_input = st.text_input(
            "GitHub Issue Number",
            placeholder="Example: 5"
        )

        submitted = st.form_submit_button(
            "Start Debugging",
            type="primary",
            use_container_width=True
        )

    # --------------------------------------------------
    # SUBMISSION PROCESS
    # --------------------------------------------------

    if submitted:

        repo_url = repo_url.strip()
        issue_number_input = issue_number_input.strip()

        # Validate repository URL
        if not _validate_repository_url(repo_url):

            st.error(
                "Invalid GitHub repository URL. "
                "Use https://github.com/owner/repository"
            )

            return

        # Validate issue number
        try:

            issue_number = int(issue_number_input)

            if issue_number <= 0:
                st.error(
                    "Issue number must be greater than zero."
                )
                return

        except ValueError:

            st.error(
                "Please enter a valid numerical issue number."
            )

            return

        # --------------------------------------------------
        # FETCH GITHUB ISSUE
        # --------------------------------------------------

        with st.spinner("Fetching GitHub issue details..."):

            issue_data = read_github_issue(
                repo_url,
                issue_number
            )

        if not isinstance(issue_data, dict):

            st.error("Invalid response from GitHub issue reader.")
            return

        if not issue_data.get("success"):

            _show_error(issue_data)
            return

        # --------------------------------------------------
        # DISPLAY ISSUE DETAILS
        # --------------------------------------------------

        st.success("GitHub issue fetched successfully!")

        st.subheader("Issue Details")

        st.markdown(
            "**Title:** {}".format(
                issue_data.get("title", "Untitled")
            )
        )

        st.write(
            "**Issue Number:**",
            issue_data.get("number")
        )

        st.write(
            "**Repository:**",
            repo_url
        )

        st.write(
            "**State:**",
            issue_data.get("state", "Unknown")
        )

        st.write(
            "**Reported By:**",
            issue_data.get("user", "Unknown")
        )

        st.write("**Description:**")

        issue_body = issue_data.get("body") or "No description provided."

        st.text_area(
            "Issue Description",
            value=issue_body,
            height=150,
            disabled=True
        )

        st.markdown(
            "[Open GitHub Issue]({})".format(
                issue_data.get("issue_url", "")
            )
        )

        st.divider()

        # --------------------------------------------------
        # START DIRECT PYTHON WORKFLOW
        # --------------------------------------------------

        with st.spinner(
            "Starting YuktiC-oreX autonomous debugging workflow..."
        ):

            result = start_debugging(
                repo_url,
                issue_number
            )

        if not isinstance(result, dict):

            st.error(
                "Invalid response from debugging workflow."
            )

            return

        # Check workflow errors
        if result.get("status") == "failed" or result.get("error"):

            _show_error(result)
            return

        task_id = result.get("task_id")

        if not task_id:

            st.error(
                "Debugging workflow did not return a task ID."
            )

            return

        # --------------------------------------------------
        # SAVE SESSION STATE
        # --------------------------------------------------

        st.session_state["task_id"] = task_id

        st.session_state["task_status"] = result.get(
            "status",
            "pending"
        )

        st.session_state["task_stage"] = result.get(
            "stage",
            "queued"
        )

        st.session_state["task_message"] = result.get(
            "message",
            "Debugging task accepted."
        )

        st.session_state["repo_url"] = repo_url

        st.session_state["issue_number"] = issue_number

        st.session_state["debug_task_response"] = result

        st.session_state["github_issue_data"] = issue_data

        # --------------------------------------------------
        # SUCCESS
        # --------------------------------------------------

        st.success(
            "YuktiC-oreX debugging task started successfully!"
        )

        st.subheader("Debugging Task Details")

        col1, col2 = st.columns(2)

        with col1:

            st.write("**Task ID**")
            st.code(task_id)

            st.write("**Repository**")
            st.write(repo_url)

        with col2:

            st.write("**Issue Number**")
            st.write(issue_number)

            st.write("**Status**")
            st.write(result.get("status", "pending"))

        st.write(
            "**Current Stage:**",
            result.get("stage", "queued")
        )

        st.info(
            "Your debugging workflow is running in the background. "
            "Open the Progress page to monitor execution."
        )

    # --------------------------------------------------
    # EXISTING TASK
    # --------------------------------------------------

    current_task_id = st.session_state.get("task_id")

    if current_task_id:

        st.divider()

        st.subheader("Current Debugging Task")

        st.code(current_task_id)

        st.write(
            "**Status:**",
            st.session_state.get("task_status", "pending")
        )

        st.write(
            "**Stage:**",
            st.session_state.get("task_stage", "queued")
        )

        st.write(
            "**Message:**",
            st.session_state.get("task_message", "")
        )
