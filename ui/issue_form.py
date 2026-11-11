
import os
import requests
import streamlit as st
from urllib.parse import urlparse


# --------------------------------------------------
# BACKEND CONFIGURATION
# --------------------------------------------------

API_BASE_URL = os.getenv(
    "YUKTICOREX_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")


# --------------------------------------------------
# ERROR HANDLING
# --------------------------------------------------

def _get_error_message(response):
    """Extract a readable error message from backend response."""

    try:
        data = response.json()

        error = data.get("error")

        if isinstance(error, dict):
            return error.get(
                "message",
                "Unable to start debugging."
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
# REPOSITORY URL VALIDATION
# --------------------------------------------------

def _validate_repository_url(repo_url: str) -> bool:
    """
    Validate a GitHub repository URL.

    Expected format:
        https://github.com/owner/repository
    """

    try:
        parsed = urlparse(repo_url.strip())

        if parsed.scheme not in ("https", "http"):
            return False

        if parsed.netloc.lower() not in (
            "github.com",
            "www.github.com"
        ):
            return False

        path_parts = [
            part for part in parsed.path.strip("/").split("/")
            if part
        ]

        if len(path_parts) != 2:
            return False

        if not all(path_parts):
            return False

        return True

    except (ValueError, AttributeError):
        return False


# --------------------------------------------------
# ISSUE SUBMISSION FORM
# --------------------------------------------------

def show_issue_form():
    """
    Display the GitHub issue submission form.

    Backend endpoint:
        POST /api/debug

    Request:
        {
            "repo_url": str,
            "issue_number": int
        }

    Response:
        {
            "task_id": str,
            "status": "pending",
            "stage": "queued",
            "message": str
        }
    """

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
            placeholder="https://github.com/owner/repository",
            help="Enter the main GitHub repository URL."
        )

        issue_number_input = st.text_input(
            "GitHub Issue Number",
            placeholder="Example: 5",
            help="Enter the numerical GitHub issue number."
        )

        submitted = st.form_submit_button(
            "Start Debugging",
            type="primary",
            use_container_width=True
        )

    # --------------------------------------------------
    # FORM SUBMISSION
    # --------------------------------------------------

    if submitted:

        repo_url = repo_url.strip()
        issue_number_input = issue_number_input.strip()

        # Validate repository URL
        if not repo_url:
            st.error("Please enter a GitHub repository URL.")

            return

        if not _validate_repository_url(repo_url):
            st.error(
                "Invalid GitHub repository URL. "
                "Use this format: "
                "https://github.com/owner/repository"
            )

            return

        # Validate issue number
        if not issue_number_input:
            st.error("Please enter a GitHub issue number.")

            return

        try:
            issue_number = int(issue_number_input)

            if issue_number <= 0:
                st.error("Issue number must be greater than zero.")
                return

        except ValueError:
            st.error("Issue number must be a valid integer.")
            return

        # --------------------------------------------------
        # BACKEND API REQUEST
        # --------------------------------------------------

        request_data = {
            "repo_url": repo_url,
            "issue_number": issue_number
        }

        st.info("Sending debugging request to backend...")

        try:

            response = requests.post(
                f"{API_BASE_URL}/api/debug",
                json=request_data,
                timeout=60
            )

            # Read JSON response
            try:
                data = response.json()

            except ValueError:
                st.error(
                    "Backend returned an invalid JSON response."
                )
                return

            # Check HTTP response
            if response.status_code not in (200, 202):

                st.error(
                    _get_error_message(response)
                )

                return

            # Validate response format
            if not isinstance(data, dict):
                st.error("Invalid response received from backend.")
                return

            task_id = data.get("task_id")

            if not task_id:
                st.error(
                    "Backend response does not contain a task_id."
                )
                return

            # --------------------------------------------------
            # SAVE TASK INFORMATION
            # --------------------------------------------------

            st.session_state["task_id"] = task_id

            st.session_state["task_status"] = data.get(
                "status",
                "pending"
            )

            st.session_state["task_stage"] = data.get(
                "stage",
                "queued"
            )

            st.session_state["task_message"] = data.get(
                "message",
                "Debugging task accepted."
            )

            st.session_state["repo_url"] = repo_url

            st.session_state["issue_number"] = issue_number

            # Save complete backend response
            st.session_state["debug_task_response"] = data

            # --------------------------------------------------
            # SUCCESS MESSAGE
            # --------------------------------------------------

            st.success(
                data.get(
                    "message",
                    "Debugging task accepted successfully."
                )
            )

            st.markdown("### Debugging Task Details")

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
                st.write(st.session_state["task_status"])

            st.write(
                "**Current Stage:**",
                st.session_state["task_stage"]
            )

            st.info(
                "Your debugging task has been registered. "
                "Open the Progress page to monitor execution."
            )

        # --------------------------------------------------
        # CONNECTION ERROR
        # --------------------------------------------------

        except requests.Timeout:
            st.error(
                "Backend request timed out. "
                "Check whether the backend is running."
            )

        except requests.ConnectionError:
            st.error(
                "Cannot connect to the backend. "
                f"Please check {API_BASE_URL}"
            )

        except requests.RequestException as exc:
            st.error(
                f"Could not submit debugging task: {exc}"
            )

    # --------------------------------------------------
    # EXISTING TASK INFORMATION
    # --------------------------------------------------

    current_task_id = st.session_state.get("task_id")

    if current_task_id and not submitted:

        st.divider()

        st.subheader("Current Debugging Task")

        st.write(
            "**Task ID:**",
            current_task_id
        )

        st.write(
            "**Status:**",
            st.session_state.get(
                "task_status",
                "pending"
            )
        )

        st.write(
            "**Stage:**",
            st.session_state.get(
                "task_stage",
                "queued"
            )
        )
