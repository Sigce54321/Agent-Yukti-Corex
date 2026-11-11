
import streamlit as st
from urllib.parse import urlparse
from ui import backend


# --------------------------------------------------
# BACKEND CONFIGURATION
# --------------------------------------------------



# --------------------------------------------------
# ERROR HANDLING
# --------------------------------------------------



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

    Calls the local workflow's asynchronous start_debugging function.

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

        st.info("Submitting debugging task to the local workflow...")

        try:

            data = backend.submit_task(st.session_state, repo_url, issue_number)
            if data.get("error") or data.get("status") == "failed":
                st.error(backend.error_message(data))
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

            if st.session_state.get("task_id") == task_id:
                # Reusing a guarded submission must not rewind polled progress
                # to the original queued response.
                data = {**data, **{
                    field: st.session_state.get(session_key, data.get(field))
                    for field, session_key in (
                        ("status", "task_status"), ("stage", "task_stage"),
                        ("message", "task_message"),
                    )
                }}

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

        except backend.BackendError as exc:
            st.error(str(exc))

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

    # Explicitly reset only the submission guard; navigation never resets it.
    if st.session_state.get("debug_submissions"):
        st.caption("Repeated submissions reuse the accepted task. Reset only when you intend to start another run.")
        if st.button("Allow another run for this issue", key="reset_debug_submission"):
            retry_url = repo_url.strip()
            try:
                retry_issue = int(issue_number_input.strip())
            except ValueError:
                st.warning("Enter the repository and issue number to reset.")
            else:
                backend.reset_submission(st.session_state, retry_url, retry_issue)
                st.info("You can now submit a new run for this issue.")
